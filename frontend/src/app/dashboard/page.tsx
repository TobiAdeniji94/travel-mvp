'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/api';
import { Itinerary } from '@/types';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Navigation from '@/components/Navigation';

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuth();
  const [itineraries, setItineraries] = useState<Itinerary[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) return;

    const loadDashboardData = async () => {
      try {
        // Load user's itineraries
        const userItineraries = await apiClient.getItineraries();
        setItineraries(userItineraries);

        // Load destination recommendations
        const destRecommendations = await apiClient.getRecommendations('destinations', {
          interests: user?.preferences?.interests || ['sightseeing', 'culture'],
          budget: user?.preferences?.budget || 1000,
          limit: 6
        });
        setRecommendations(destRecommendations);
      } catch (error) {
        console.error('Error loading dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [isAuthenticated, user]);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Welcome to The Calm Route</h1>
          <p className="text-gray-600 mb-8">Please sign in to access your dashboard</p>
          <div className="space-x-4">
            <Link href="/login">
              <Button>Sign In</Button>
            </Link>
            <Link href="/register">
              <Button variant="outline">Sign Up</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex items-center justify-center pt-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome back, {user?.username}!
          </h1>
          <p className="mt-2 text-gray-600">
            Ready to plan your next adventure?
          </p>
        </div>

        {/* Quick Actions */}
        <div className="mb-8 flex flex-col sm:flex-row gap-4">
          <Link href="/itinerary/new">
            <Button size="lg" className="w-full sm:w-auto">
              <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Plan New Trip
            </Button>
          </Link>
          {itineraries.length > 0 && (
            <Link href={`/itinerary/${itineraries[0].id}`}>
              <Button variant="outline" size="lg" className="w-full sm:w-auto">
                Continue Last Trip
              </Button>
            </Link>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* My Trips Section */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">My Trips</h2>
              {itineraries.length > 3 && (
                <Link href="/itineraries" className="text-blue-600 hover:text-blue-500 text-sm font-medium">
                  View all
                </Link>
              )}
            </div>

            {itineraries.length === 0 ? (
              <Card>
                <CardContent className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No trips yet</h3>
                  <p className="text-gray-500 mb-6">Start planning your first adventure!</p>
                  <Link href="/itinerary/new">
                    <Button>Create Your First Trip</Button>
                  </Link>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {itineraries.slice(0, 4).map((itinerary) => (
                  <Card key={itinerary.id} className="hover:shadow-md transition-shadow cursor-pointer">
                    <Link href={`/itinerary/${itinerary.id}`}>
                      <CardHeader>
                        <CardTitle className="text-lg">{itinerary.title || itinerary.destination}</CardTitle>
                        <CardDescription>
                          {new Date(itinerary.start_date).toLocaleDateString()} - {new Date(itinerary.end_date).toLocaleDateString()}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            itinerary.status === 'confirmed' ? 'bg-green-100 text-green-800' :
                            itinerary.status === 'draft' ? 'bg-yellow-100 text-yellow-800' :
                            itinerary.status === 'completed' ? 'bg-blue-100 text-blue-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {itinerary.status}
                          </span>
                          {itinerary.budget && (
                            <span className="text-sm text-gray-500">
                              ${itinerary.budget}
                            </span>
                          )}
                        </div>
                      </CardContent>
                    </Link>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* Recommendations Section */}
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Recommended for You</h2>
            
            {recommendations.length === 0 ? (
              <Card>
                <CardContent className="text-center py-8">
                  <p className="text-gray-500">Loading recommendations...</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {recommendations.slice(0, 4).map((destination, index) => (
                  <Card key={index} className="hover:shadow-md transition-shadow">
                    <CardContent className="p-4">
                      <div className="flex items-start space-x-3">
                        <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                          <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-medium text-gray-900 truncate">
                            {destination.name}
                          </h3>
                          <p className="text-sm text-gray-500 truncate">
                            {destination.city}, {destination.country}
                          </p>
                          {destination.rating && (
                            <div className="flex items-center mt-1">
                              <span className="text-xs text-yellow-600">★</span>
                              <span className="text-xs text-gray-500 ml-1">{destination.rating}</span>
                            </div>
                          )}
                        </div>
                        <Button size="sm" variant="outline">
                          Add to Trip
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
