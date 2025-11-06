export async function POST(req) {
    try {
    const formData = await req.json();

    const response = await fetch(`${process.env.NEXT_PUBLIC_API_PYTHON_ML_SERVER}/heart-disease/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });

    const data = await response.json();

    return new Response(JSON.stringify(data), { status: 200 });
  } catch (err) {
    console.error('Error in Next.js API route:', err);
    return new Response(JSON.stringify({ success: false, error: err.message }), { status: 500 });
  }
}