'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Heart, Activity, TrendingUp, Plus, ArrowRight, UserSearch, Home, ShoppingCart } from 'lucide-react';

// Local static model configuration (optional custom colors/icons)
const localModelConfig = [
	{ id: 1, path: '/medical-charge-prediction', icon: Activity, color: 'from-purple-500 to-indigo-600' },
	{ id: 2, path: '/heart-disease-prediction', icon: Heart, color: 'from-red-500 to-pink-600' },
	{ id: 3, path: '/customer-churn-prediction', icon: UserSearch, color: 'from-yellow-500 to-orange-600' },
	{ id: 4, path: '/house-price-estimator', icon: Home, color: 'from-green-500 to-teal-600' },
	{ id: 5, path: '/uplift-model', icon: ShoppingCart, color: 'from-green-500 to-teal-600' },
];

// Helper function to extract pathname from live_url
const extractPath = (url) => {
	try {
		const urlObject = new URL(url);
		return urlObject.pathname;
	} catch (e) {
		console.error("Invalid URL in live_url:", url, e);
		return url;
	}
};

// Helper function to compare two arrays deeply
const areArraysEqual = (arr1, arr2) => {
	if (!arr1 || !arr2) return false;
	if (arr1.length !== arr2.length) return false;
	return JSON.stringify(arr1) === JSON.stringify(arr2);
};

// Helper function to load cached data from localStorage
const loadCachedData = () => {
	try {
		const cached = localStorage.getItem('ml_models_cache');
		if (cached) {
			return JSON.parse(cached);
		}
		return null;
	} catch (error) {
		console.error("Error loading cached data:", error);
		return null;
	}
};

// Helper function to save data to localStorage
const saveCachedData = (data) => {
	try {
		localStorage.setItem('ml_models_cache', JSON.stringify(data));
		return true;
	} catch (error) {
		console.error("Error saving cached data:", error);
		return false;
	}
};

export default function MLModelsHomepage() {
	const [hoveredCard, setHoveredCard] = useState(null);
	const [models, setModels] = useState([]);
	const [isLoading, setIsLoading] = useState(true);

	const processModels = (fetchedData) => {
		// Filter for ML category + skip if live_url is empty, null, or invalid
		const mlProjects = fetchedData.filter(
			(project) =>
				project.category === "Machine Learning" &&
				project.liveUrl &&
				project.liveUrl.trim() !== ""
		);

		const mergedModels = mlProjects.map((fetchedModel) => {
			const modelPath = extractPath(fetchedModel.liveUrl);
			const config = localModelConfig.find((c) => c.path === modelPath);

			const accuracyValue = fetchedModel.modelAccuracy
				? `${Math.round(fetchedModel.modelAccuracy)}% Accuracy`
				: 'N/A';

			const featuresValue = fetchedModel.modelFeatures
				? `${Math.round(fetchedModel.modelFeatures)} Features`
				: 'N/A';

			// Convert backend URL into frontend route
			const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
			const fullFrontendPath = `${baseUrl}${modelPath}`;
			
			return {
				name: fetchedModel.title,
				description: fetchedModel.description,
				path: fullFrontendPath,
				stats: featuresValue,
				accuracy: accuracyValue,
				id: config?.id || fetchedModel.id,
				icon: config?.icon || Plus,
				color: config?.color || 'from-gray-500 to-gray-600',
				fetched:fetchedModel,
			};
		});

		return mergedModels;
	};

	const fetchAndMergeModels = async () => {
		setIsLoading(true);
		try {
			// Step 1: Try to load cached data first
			const cachedData = loadCachedData();
			
			if (cachedData) {
				console.log("Loading from localStorage cache...");
				// Process and display cached data immediately
				const processedModels = processModels(cachedData);
				setModels(processedModels);
				setIsLoading(false);
			}

			// Step 2: Fetch fresh data from API
			const response = await fetch(`${process.env.NEXT_PUBLIC_API_PORTFOLIO_SERVER}/project/projects_data`);
			const Data = await response.json();
			const fetchedData = Data.data;
			console.log("Fetched data from API:", fetchedData);

			// Step 3: Compare with cached data
			if (cachedData) {
				const hasChanges = !areArraysEqual(cachedData, fetchedData);
				
				if (hasChanges) {
					console.log("Changes detected! Updating localStorage and reloading...");
					// Save new data to localStorage
					saveCachedData(fetchedData);
					// Reload the page to reflect changes
					window.location.reload();
					return;
				} else {
					console.log("No changes detected. Using cached data.");
					return;
				}
			} else {
				// No cache exists, save the fetched data
				console.log("No cache found. Saving fetched data to localStorage...");
				saveCachedData(fetchedData);
				const processedModels = processModels(fetchedData);
				setModels(processedModels);
			}
		} catch (error) {
			console.error("Error fetching or merging model data:", error);
			setModels([]);
		} finally {
			setIsLoading(false);
		}
	};

	useEffect(() => {
		fetchAndMergeModels();
	}, []);

	const maxSlots = 4;
	const modelCount = models.length;
	const emptySlots = Array(Math.max(0, maxSlots - modelCount)).fill(null);

	return (
		<div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
			<div className="absolute inset-0 overflow-hidden">
				<div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
				<div className="absolute -bottom-40 -left-40 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
				<div className="absolute top-1/2 left-1/2 w-80 h-80 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
			</div>

			<div className="relative z-10">
				<div className="text-center py-16 px-4 md:py-24">
					<div className="inline-block mb-4">
						<span className="px-4 py-2 bg-purple-500/20 border border-purple-500/50 rounded-full text-purple-300 text-sm font-semibold">
							AI-Powered Predictions
						</span>
					</div>

					<h1 className="text-5xl md:text-7xl font-bold text-white mb-6 tracking-tight">
						Machine Learning Models
					</h1>

					<p className="text-xl md:text-2xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
						Explore advanced ML models designed to provide predictions and data-driven insights across various domains.
					</p>
				</div>

				<div className="max-w-7xl mx-auto px-4 pb-24">
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
						{isLoading ? (
							Array(4)
								.fill(0)
								.map((_, index) => (
									<div
										key={index}
										className="h-64 bg-white/5 backdrop-blur-md border border-white/20 rounded-2xl p-6 animate-pulse"
									>
										<div className="w-10 h-10 bg-white/20 rounded-xl mb-4"></div>
										<div className="h-5 bg-white/20 rounded w-3/4 mb-3"></div>
										<div className="space-y-2">
											<div className="h-3 bg-white/10 rounded w-full"></div>
											<div className="h-3 bg-white/10 rounded w-5/6"></div>
										</div>
										<div className="flex gap-4 mt-6">
											<div className="h-4 bg-white/20 rounded w-1/4"></div>
											<div className="h-4 bg-white/20 rounded w-1/4"></div>
										</div>
									</div>
								))
						) : (
							models.map((model) => {
								const IconComponent = model.icon || Plus;
								return (
									<Link href={model.path} key={model.id}>
										<div
											className="h-full cursor-pointer group"
											onMouseEnter={() => setHoveredCard(model.id)}
											onMouseLeave={() => setHoveredCard(null)}
										>
											<div className="relative h-full bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-6 overflow-hidden transition-all duration-300 hover:border-white/40 hover:bg-white/15 hover:shadow-2xl">
												<div className={`absolute inset-0 bg-gradient-to-br ${model.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}></div>

												<div className="relative z-10">
													<div className={`mb-4 p-4 bg-gradient-to-br ${model.color} rounded-xl inline-block`}>
														<IconComponent className="w-8 h-8 text-white" />
													</div>

													<h3 className="text-xl font-bold text-white mb-3 group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-white group-hover:to-gray-200 transition-all duration-300">
														{model.name}
													</h3>

													<p className="text-gray-300 text-sm mb-6 line-clamp-3 group-hover:text-gray-200 transition-colors duration-300">
														{model.description}
													</p>

													<div className="flex gap-4 mb-6 pb-6 border-b border-white/10">
														<div>
															<p className="text-xs text-gray-400 uppercase tracking-wide">Features</p>
															<p className="text-lg font-semibold text-white">{model.stats}</p>
														</div>
														<div>
															<p className="text-xs text-gray-400 uppercase tracking-wide">Accuracy</p>
															<p className="text-lg font-semibold text-white">{model.accuracy}</p>
														</div>
													</div>

													<div className="flex items-center justify-between">
														<span className="text-purple-300 font-semibold text-sm">Explore Model</span>
														<ArrowRight
															className={`w-5 h-5 text-purple-300 transition-all duration-300 ${
																hoveredCard === model.id ? 'translate-x-1' : ''
															}`}
														/>
													</div>
												</div>

												<div className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
													<div className={`absolute inset-0 bg-gradient-to-r ${model.color} rounded-2xl opacity-20 blur`}></div>
												</div>
											</div>
										</div>
									</Link>
								);
							})
						)}

						{!isLoading &&
							emptySlots.map((_, index) => (
								<div key={`empty-${index}`} className="h-full">
									<div className="relative h-full bg-white/5 backdrop-blur-md border-2 border-dashed border-white/20 rounded-2xl p-6 flex flex-col items-center justify-center hover:border-white/40 hover:bg-white/10 transition-all duration-300 cursor-pointer group">
										<div className="p-4 bg-white/10 rounded-xl mb-4 group-hover:bg-white/20 transition-all duration-300">
											<Plus className="w-8 h-8 text-white/50 group-hover:text-white/70 transition-colors duration-300" />
										</div>

										<p className="text-center text-gray-400 text-sm font-medium group-hover:text-gray-300 transition-colors duration-300">
											Coming Soon
										</p>
										<p className="text-center text-gray-500 text-xs mt-2">
											New model will be added here
										</p>

										<div className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
											<div className="absolute inset-0 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl opacity-10 blur"></div>
										</div>
									</div>
								</div>
							))}
					</div>
				</div>
			</div>
		</div>
	);
}