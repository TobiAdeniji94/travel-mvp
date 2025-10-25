'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/api';
import { NLPParseResult, TravelPreferences } from '@/types';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Navigation from '@/components/Navigation';

export default function NewItineraryPage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  
  // Step 1: Natural Language Input
  const [travelText, setTravelText] = useState('');
  const [parseResult, setParseResult] = useState<NLPParseResult | null>(null);
  
  // Step 2: Refined Preferences
  const [preferences, setPreferences] = useState<TravelPreferences>({
    interests: [],
    budget: 1000,
    travel_style: [],
    pace: 'moderate',
  });
  
  // Step 3: Generated Itinerary
  const [generatedItinerary, setGeneratedItinerary] = useState<any>(null);
  // Optional: enable Transformer ordering per request
  const [useTransformer, setUseTransformer] = useState<boolean>(false);

  if (!isAuthenticated) {
    router.push('/login');
    return null;
  }

  const handleParseTravel = async () => {
    if (!travelText.trim()) return;
    
    setLoading(true);
    try {
      const result = await apiClient.parseTravel(travelText);
      setParseResult(result);
      
      // Pre-fill preferences from parsed data
      if (result.parsed_data) {
        setPreferences(prev => ({
          ...prev,
          interests: result.parsed_data.interests || prev.interests,
          budget: result.parsed_data.budget || prev.budget,
          travel_style: result.parsed_data.travel_style || prev.travel_style,
        }));
      }
      
      setStep(2);
    } catch (error) {
      console.error('Error parsing travel request:', error);
      alert('Failed to parse your travel request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateItinerary = async () => {
    setLoading(true);
    try {
      const itinerary = await apiClient.createItinerary({
        text: travelText,
        preferences: preferences,
        use_transformer: useTransformer,
      });
      setGeneratedItinerary(itinerary);
      setStep(3);
    } catch (error) {
      console.error('Error generating itinerary:', error);
      alert('Failed to generate itinerary. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveItinerary = async () => {
    if (generatedItinerary) {
      router.push(`/itinerary/${generatedItinerary.id}`);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      
      <main className="max-w-4xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-center space-x-4">
            {[1, 2, 3].map((stepNumber) => (
              <div key={stepNumber} className="flex items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  step >= stepNumber 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-600'
                }`}>
                  {stepNumber}
                </div>
                {stepNumber < 3 && (
                  <div className={`w-16 h-1 mx-2 ${
                    step > stepNumber ? 'bg-blue-600' : 'bg-gray-200'
                  }`} />
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-center mt-4">
            <span className="text-sm text-gray-600">
              {step === 1 && 'Describe your trip'}
              {step === 2 && 'Refine preferences'}
              {step === 3 && 'Review itinerary'}
            </span>
          </div>
        </div>

        {/* Step 1: Natural Language Input */}
        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Describe Your Dream Trip</CardTitle>
              <CardDescription>
                Tell us about your ideal vacation in your own words. Our AI will understand your preferences and create a personalized itinerary.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  What kind of trip are you planning?
                </label>
                <textarea
                  value={travelText}
                  onChange={(e) => setTravelText(e.target.value)}
                  placeholder="Example: I want to visit Paris for 5 days in March with a budget of $3000. I love art museums, local cuisine, and romantic walks. I prefer a relaxed pace with 4-star accommodations."
                  className="w-full h-32 p-3 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 resize-none"
                />
              </div>
              
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">💡 Tips for better results:</h4>
                <ul className="text-sm text-blue-800 space-y-1">
                  <li>• Mention your destination and travel dates</li>
                  <li>• Include your budget range</li>
                  <li>• Describe your interests and preferred activities</li>
                  <li>• Specify your travel style (relaxed, adventurous, luxury, etc.)</li>
                </ul>
              </div>

              <Button
                onClick={handleParseTravel}
                loading={loading}
                disabled={!travelText.trim()}
                className="w-full"
                size="lg"
              >
                Parse My Travel Request
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Refine Preferences */}
        {step === 2 && parseResult && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Parsed Information</CardTitle>
                <CardDescription>
                  Here's what we understood from your request. You can refine these details below.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-900">
                    {parseResult.parsed_data.destination && (
                      <div>
                        <span className="font-medium">Destination:</span> {parseResult.parsed_data.destination}
                      </div>
                    )}
                    {parseResult.parsed_data.budget && (
                      <div>
                        <span className="font-medium">Budget:</span> ${parseResult.parsed_data.budget}
                      </div>
                    )}
                    {parseResult.parsed_data.duration && (
                      <div>
                        <span className="font-medium">Duration:</span> {parseResult.parsed_data.duration} days
                      </div>
                    )}
                    {parseResult.parsed_data.interests && parseResult.parsed_data.interests.length > 0 && (
                      <div>
                        <span className="font-medium">Interests:</span> {parseResult.parsed_data.interests.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Refine Your Preferences</CardTitle>
                <CardDescription>
                  Adjust these settings to get the perfect itinerary for your trip.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Budget (USD)
                  </label>
                  <Input
                    type="number"
                    value={preferences.budget}
                    onChange={(e) => setPreferences(prev => ({ ...prev, budget: Number(e.target.value) }))}
                    min={0}
                  />
                </div>

                {/* Transformer ordering toggle */}
                <div className="flex items-center space-x-3">
                  <input
                    id="use-transformer"
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    checked={useTransformer}
                    onChange={(e) => setUseTransformer(e.target.checked)}
                  />
                  <label htmlFor="use-transformer" className="text-sm text-gray-700">
                    Enable AI ordering (Transformer)
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Travel Pace
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['relaxed', 'moderate', 'intense'] as const).map((pace) => (
                      <button
                        key={pace}
                        onClick={() => setPreferences(prev => ({ ...prev, pace }))}
                        className={`p-3 text-sm font-medium rounded-lg border transition-colors ${
                          preferences.pace === pace
                            ? 'border-blue-500 bg-blue-50 text-blue-700'
                            : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        {pace.charAt(0).toUpperCase() + pace.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Interests
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {['sightseeing', 'culture', 'food', 'nightlife', 'nature', 'adventure', 'relaxation', 'shopping', 'history', 'art'].map((interest) => (
                      <button
                        key={interest}
                        onClick={() => {
                          setPreferences(prev => ({
                            ...prev,
                            interests: prev.interests.includes(interest)
                              ? prev.interests.filter(i => i !== interest)
                              : [...prev.interests, interest]
                          }));
                        }}
                        className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                          preferences.interests.includes(interest)
                            ? 'border-blue-500 bg-blue-50 text-blue-700'
                            : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        {interest}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex space-x-4">
                  <Button
                    variant="outline"
                    onClick={() => setStep(1)}
                    className="flex-1"
                  >
                    Back
                  </Button>
                  <Button
                    onClick={handleGenerateItinerary}
                    loading={loading}
                    className="flex-1"
                  >
                    Generate Itinerary
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Step 3: Generated Itinerary */}
        {step === 3 && generatedItinerary && (
          <Card>
            <CardHeader>
              <CardTitle>Your Personalized Itinerary</CardTitle>
              <CardDescription>
                Here's your AI-generated travel plan. You can save it and make further adjustments.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="font-medium text-green-900 mb-2">🎉 Itinerary Generated Successfully!</h3>
                <p className="text-sm text-green-800">
                  Your personalized travel plan is ready. You can now save it and view the full details.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Trip Overview</h4>
                  <div className="space-y-2 text-sm text-gray-600">
                    <div>Destination: {generatedItinerary.destination}</div>
                    <div>Duration: {generatedItinerary.duration || 'Multiple'} days</div>
                    <div>Budget: ${generatedItinerary.budget || preferences.budget}</div>
                    <div>Status: {generatedItinerary.status}</div>
                  </div>
                </div>
                
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Included</h4>
                  <div className="space-y-1 text-sm text-gray-600">
                    <div>✓ Destinations & Activities</div>
                    <div>✓ Accommodation Suggestions</div>
                    <div>✓ Transportation Options</div>
                    <div>✓ Day-by-day Schedule</div>
                  </div>
                </div>
              </div>

              <div className="flex space-x-4">
                <Button
                  variant="outline"
                  onClick={() => setStep(2)}
                  className="flex-1"
                >
                  Back to Preferences
                </Button>
                <Button
                  onClick={handleSaveItinerary}
                  className="flex-1"
                >
                  Save & View Itinerary
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
