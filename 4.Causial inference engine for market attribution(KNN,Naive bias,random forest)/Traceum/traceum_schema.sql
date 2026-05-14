-- ============================================================
--  TRACEUM — User Behavioral Data Schema
--  Stack: Next.js + NestJS + FastAPI + PostgreSQL
--  Purpose: Real-time f0–f11 feature tracking for PSM model
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ============================================================
--  TABLE 1: users
--  One row per anonymous user/session.
--  Created the moment a user first lands on the site.
-- ============================================================
CREATE TABLE users (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          VARCHAR(64) NOT NULL UNIQUE,          -- anonymous browser fingerprint
    device_type         SMALLINT    NOT NULL DEFAULT 0,       -- 0=desktop, 1=mobile, 2=tablet
    referral_source     VARCHAR(128),                         -- utm_source / direct / organic
    country_code        CHAR(2),                              -- ISO 3166-1 alpha-2
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_session  ON users (session_id);
CREATE INDEX idx_users_last_seen ON users (last_seen_at);


-- ============================================================
--  TABLE 2: events
--  Every raw behavioral event streamed from the frontend.
--  High-write table — kept lean on purpose.
-- ============================================================
CREATE TYPE event_type AS ENUM (
    'page_view',
    'click',
    'scroll',
    'add_to_cart',
    'remove_from_cart',
    'checkout_start',
    'checkout_complete',  -- this is the "conversion" outcome
    'search',
    'product_view',
    'wishlist_add',
    'session_end'
);

CREATE TABLE events (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event           event_type  NOT NULL,
    page            VARCHAR(256),                             -- /products/shoes-42
    product_id      VARCHAR(64),                             -- if event is product-related
    category        VARCHAR(64),                             -- product category
    value           NUMERIC(10,2),                           -- cart value at time of event
    scroll_pct      SMALLINT,                                -- 0–100, only for scroll events
    duration_ms     INT,                                     -- time spent on page (ms)
    metadata        JSONB,                                   -- any extra data, flexible
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_user_id    ON events (user_id);
CREATE INDEX idx_events_created_at ON events (created_at DESC);
CREATE INDEX idx_events_type       ON events (event);


-- ============================================================
--  TABLE 3: user_features
--  The ML feature vector (f0–f11) per user.
--  Updated in real time by a trigger on the events table.
--  This is what NestJS reads and sends to FastAPI via gRPC.
-- ============================================================
CREATE TABLE user_features (
    user_id             UUID        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,

    -- f0: total items currently in cart
    f0_cart_items       SMALLINT    NOT NULL DEFAULT 0,

    -- f1: total cart value (sum of all add_to_cart values)
    f1_cart_value       NUMERIC(10,2) NOT NULL DEFAULT 0.00,

    -- f2: number of distinct product categories browsed
    f2_categories_seen  SMALLINT    NOT NULL DEFAULT 0,

    -- f3: number of product pages viewed
    f3_product_views    INT         NOT NULL DEFAULT 0,

    -- f4: number of searches performed
    f4_search_count     SMALLINT    NOT NULL DEFAULT 0,

    -- f5: total session duration in seconds (sum across all page events)
    f5_session_duration INT         NOT NULL DEFAULT 0,

    -- f6: scroll depth score (avg scroll_pct across all scroll events, 0–100)
    f6_scroll_depth     NUMERIC(5,2) NOT NULL DEFAULT 0.00,

    -- f7: number of wishlist adds
    f7_wishlist_adds    SMALLINT    NOT NULL DEFAULT 0,

    -- f8: total click count
    f8_click_count      INT         NOT NULL DEFAULT 0,

    -- f9: number of checkout attempts (checkout_start events)
    f9_checkout_starts  SMALLINT    NOT NULL DEFAULT 0,

    -- f10: device type (mirrors users.device_type, denormalised for fast reads)
    f10_device_type     SMALLINT    NOT NULL DEFAULT 0,

    -- f11: referral source encoded (0=direct, 1=organic, 2=paid, 3=social, 4=email)
    f11_referral_encoded SMALLINT   NOT NULL DEFAULT 0,

    -- meta
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
--  TABLE 4: user_outcomes
--  Did the treatment (offer/ad) work?
--  Written by NestJS after FastAPI returns a score.
--  Used as training data for weekly model retraining.
-- ============================================================
CREATE TABLE user_outcomes (
    id                  BIGSERIAL   PRIMARY KEY,
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    propensity_score    NUMERIC(6,4),                        -- score returned by FastAPI
    treatment           SMALLINT    NOT NULL DEFAULT 0,      -- 0=no offer shown, 1=offer shown
    converted           SMALLINT    NOT NULL DEFAULT 0,      -- 0=no, 1=yes (checkout_complete)
    offer_type          VARCHAR(64),                         -- 'discount_10', 'free_shipping', etc.
    scored_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    converted_at        TIMESTAMPTZ                          -- NULL until conversion happens
);

CREATE INDEX idx_outcomes_user_id   ON user_outcomes (user_id);
CREATE INDEX idx_outcomes_scored_at ON user_outcomes (scored_at DESC);
CREATE INDEX idx_outcomes_treatment ON user_outcomes (treatment, converted);


-- ============================================================
--  FUNCTION: refresh_user_features()
--  Called by trigger after every INSERT into events.
--  Recomputes the relevant feature(s) for that user on the fly.
-- ============================================================
CREATE OR REPLACE FUNCTION refresh_user_features()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_features (user_id, f10_device_type, f11_referral_encoded)
    SELECT
        NEW.user_id,
        u.device_type,
        CASE u.referral_source
            WHEN 'direct'   THEN 0
            WHEN 'organic'  THEN 1
            WHEN 'paid'     THEN 2
            WHEN 'social'   THEN 3
            WHEN 'email'    THEN 4
            ELSE 0
        END
    FROM users u WHERE u.id = NEW.user_id
    ON CONFLICT (user_id) DO UPDATE SET
        -- f0: cart items = add_to_cart minus remove_from_cart counts
        f0_cart_items = (
            SELECT COALESCE(SUM(CASE WHEN event='add_to_cart' THEN 1
                                     WHEN event='remove_from_cart' THEN -1
                                     ELSE 0 END), 0)
            FROM events WHERE user_id = NEW.user_id
        ),
        -- f1: latest cart value from most recent add_to_cart
        f1_cart_value = (
            SELECT COALESCE(value, 0) FROM events
            WHERE user_id = NEW.user_id AND event = 'add_to_cart'
            ORDER BY created_at DESC LIMIT 1
        ),
        -- f2: distinct categories browsed
        f2_categories_seen = (
            SELECT COUNT(DISTINCT category) FROM events
            WHERE user_id = NEW.user_id AND category IS NOT NULL
        ),
        -- f3: product page views
        f3_product_views = (
            SELECT COUNT(*) FROM events
            WHERE user_id = NEW.user_id AND event = 'product_view'
        ),
        -- f4: searches
        f4_search_count = (
            SELECT COUNT(*) FROM events
            WHERE user_id = NEW.user_id AND event = 'search'
        ),
        -- f5: total session duration in seconds
        f5_session_duration = (
            SELECT COALESCE(SUM(duration_ms) / 1000, 0) FROM events
            WHERE user_id = NEW.user_id AND duration_ms IS NOT NULL
        ),
        -- f6: average scroll depth
        f6_scroll_depth = (
            SELECT COALESCE(AVG(scroll_pct), 0) FROM events
            WHERE user_id = NEW.user_id AND scroll_pct IS NOT NULL
        ),
        -- f7: wishlist adds
        f7_wishlist_adds = (
            SELECT COUNT(*) FROM events
            WHERE user_id = NEW.user_id AND event = 'wishlist_add'
        ),
        -- f8: total clicks
        f8_click_count = (
            SELECT COUNT(*) FROM events
            WHERE user_id = NEW.user_id AND event = 'click'
        ),
        -- f9: checkout attempts
        f9_checkout_starts = (
            SELECT COUNT(*) FROM events
            WHERE user_id = NEW.user_id AND event = 'checkout_start'
        ),
        last_updated_at = NOW();

    -- Also bump last_seen_at on users table
    UPDATE users SET last_seen_at = NOW() WHERE id = NEW.user_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
--  TRIGGER: fires after every new event row
-- ============================================================
CREATE TRIGGER trg_refresh_features
AFTER INSERT ON events
FOR EACH ROW
EXECUTE FUNCTION refresh_user_features();


-- ============================================================
--  FUNCTION: mark_conversion()
--  Call this when a checkout_complete event is inserted.
--  Updates user_outcomes so the retraining dataset is accurate.
-- ============================================================
CREATE OR REPLACE FUNCTION mark_conversion()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.event = 'checkout_complete' THEN
        UPDATE user_outcomes
        SET converted = 1,
            converted_at = NOW()
        WHERE user_id = NEW.user_id
          AND converted = 0
          AND converted_at IS NULL
          AND scored_at > NOW() - INTERVAL '24 hours'; -- only recent scoring window
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_mark_conversion
AFTER INSERT ON events
FOR EACH ROW
EXECUTE FUNCTION mark_conversion();


-- ============================================================
--  VIEW: ml_training_data
--  Joins features + outcomes for the weekly retraining job.
--  FastAPI reads this view directly with SQLAlchemy.
-- ============================================================
CREATE OR REPLACE VIEW ml_training_data AS
SELECT
    uf.f0_cart_items          AS f0,
    uf.f1_cart_value          AS f1,
    uf.f2_categories_seen     AS f2,
    uf.f3_product_views       AS f3,
    uf.f4_search_count        AS f4,
    uf.f5_session_duration    AS f5,
    uf.f6_scroll_depth        AS f6,
    uf.f7_wishlist_adds       AS f7,
    uf.f8_click_count         AS f8,
    uf.f9_checkout_starts     AS f9,
    uf.f10_device_type        AS f10,
    uf.f11_referral_encoded   AS f11,
    uo.treatment,
    uo.converted              AS conversion,
    uo.propensity_score,
    uo.scored_at
FROM user_features uf
JOIN user_outcomes uo ON uo.user_id = uf.user_id
WHERE uo.scored_at > NOW() - INTERVAL '90 days';  -- rolling 90-day window


-- ============================================================
--  VIEW: realtime_feature_vector
--  What NestJS queries to build the gRPC payload for FastAPI.
-- ============================================================
CREATE OR REPLACE VIEW realtime_feature_vector AS
SELECT
    u.session_id,
    uf.user_id,
    ARRAY[
        uf.f0_cart_items::float,
        uf.f1_cart_value::float,
        uf.f2_categories_seen::float,
        uf.f3_product_views::float,
        uf.f4_search_count::float,
        uf.f5_session_duration::float,
        uf.f6_scroll_depth::float,
        uf.f7_wishlist_adds::float,
        uf.f8_click_count::float,
        uf.f9_checkout_starts::float,
        uf.f10_device_type::float,
        uf.f11_referral_encoded::float
    ] AS feature_vector,
    uf.last_updated_at
FROM user_features uf
JOIN users u ON u.id = uf.user_id;
