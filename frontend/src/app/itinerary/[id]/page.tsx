'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/api';
import { Itinerary } from '@/types';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Navigation from '@/components/Navigation';

export default function ItineraryDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regenLoadingDay, setRegenLoadingDay] = useState<number | null>(null);
  const [publicLink, setPublicLink] = useState<string | null>(null);
  const [constraints, setConstraints] = useState<Record<number, { maxStops?: number; maxPrice?: number }>>({});

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }

    if (!id) return;

    const loadItinerary = async () => {
      try {
        const data = await apiClient.getItinerary(id as string);
        console.log('Itinerary loaded:',data);
        setItinerary(data);
      } catch (error: any) {
        if (error.status === 404) {
          setError('Itinerary not found');
        } else {
          setError('Failed to load itinerary');
        }
        console.error('Error loading itinerary:', error);
      } finally {
        setLoading(false);
      }
    };

    loadItinerary();
  }, [id, isAuthenticated, router]);

  const handleRegenerateDay = async (dayIndex: number) => {
    if (!itinerary) return;
    try {
      setRegenLoadingDay(dayIndex);
      const c = constraints[dayIndex] || {};
      const resp = await apiClient.regenerateItineraryDay(itinerary.id, {
        day_index: dayIndex,
        max_stops: c.maxStops,
        max_price_per_activity: c.maxPrice,
      });
      setItinerary(resp as any);
    } catch (e) {
      console.error('Failed to regenerate day', e);
      alert('Failed to regenerate this day');
    } finally {
      setRegenLoadingDay(null);
    }
  };

  const handleCreateShareLink = async () => {
    if (!itinerary) return;
    try {
      const { url } = await apiClient.createShareLink(itinerary.id);
      setPublicLink(url);
      try {
        await navigator.clipboard.writeText(url);
        alert('Share link copied to clipboard');
      } catch {
        // ignore
      }
    } catch (e) {
      console.error('Failed to create share link', e);
      alert('Failed to create share link');
    }
  };

  const handleShare = async () => {
    // Check if running in browser
    if (typeof window === 'undefined') return;
    
    const currentUrl = window.location.href;
    
    if (navigator.share) {
      try {
        await navigator.share({
          title:
            (itinerary?.name as string) ||
            (itinerary?.title as string) ||
            `Trip to ${
              (itinerary?.destination as string) ||
              (itinerary?.data?.parsed_data?.destination as string) ||
              (itinerary?.data?.locations?.[0] as string) ||
              'your destination'
            }`,
          text: `Check out my travel itinerary!`,
          url: currentUrl,
        });
      } catch (error) {
        console.log('Error sharing:', error);
      }
    } else {
      // Fallback: copy to clipboard
      navigator.clipboard.writeText(currentUrl);
      alert('Link copied to clipboard!');
    }
  };

  const handleDelete = async () => {
    if (!itinerary || !confirm('Are you sure you want to delete this itinerary?')) return;

    try {
      await apiClient.deleteItinerary(itinerary.id);
      router.push('/dashboard');
    } catch (error) {
      console.error('Error deleting itinerary:', error);
      alert('Failed to delete itinerary');
    }
  };

  if (!isAuthenticated) return null;

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

  if (error || !itinerary) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-4xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <Card>
            <CardContent className="text-center py-12">
              <div className="text-red-500 mb-4">
                <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">{error}</h3>
              <Button onClick={() => router.push('/dashboard')}>
                Back to Dashboard
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      
      <main className="max-w-6xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {(
                  itinerary.name ||
                  itinerary.title ||
                  `Trip to ${
                    itinerary.destination ||
                    itinerary?.data?.parsed_data?.destination ||
                    itinerary?.data?.locations?.[0] ||
                    'your destination'
                  }`
                )}
              </h1>
              <p className="mt-2 text-gray-600">
                {new Date(itinerary.start_date).toLocaleDateString()} - {new Date(itinerary.end_date).toLocaleDateString()}
              </p>
            </div>
            <div className="flex space-x-3">
              <Button variant="outline" onClick={handleShare}>
                <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 
                  12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 
                  110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 
                  2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
                </svg>
                Share
              </Button>
              <Button variant="outline">
                Edit
              </Button>
              <Button variant="destructive" onClick={handleDelete}>
                Delete
              </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Trip Overview */}
            <Card>
              <CardHeader>
                <CardTitle>Trip Overview</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{itinerary.destination}</div>
                    <div className="text-sm text-gray-500">Destination</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {Math.ceil((new Date(itinerary.end_date).getTime() - new Date(itinerary.start_date).getTime()) / (1000 * 60 * 60 * 24))}
                    </div>
                    <div className="text-sm text-gray-500">Days</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {itinerary.budget ? `$${itinerary.budget}` : 'N/A'}
                    </div>
                    <div className="text-sm text-gray-500">Budget</div>
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${
                      itinerary.status === 'confirmed' ? 'text-green-600' :
                      itinerary.status === 'draft' ? 'text-yellow-600' :
                      itinerary.status === 'completed' ? 'text-blue-600' :
                      'text-gray-600'
                    }`}>
                      {itinerary.status.charAt(0).toUpperCase() + itinerary.status.slice(1)}
                    </div>
                    <div className="text-sm text-gray-500">Status</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Interactive Map Placeholder */}
            <Card>
              <CardHeader>
                <CardTitle>Trip Map</CardTitle>
                <CardDescription>
                  Interactive map showing your destinations and route
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="bg-gray-100 rounded-lg h-64 flex items-center justify-center">
                  <div className="text-center text-gray-500">
                    <svg className="mx-auto h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-1.447-.894L15 4m0 13V4m-6 3l6-3" />
                    </svg>
                    <p>Interactive map coming soon</p>
                    <p className="text-sm">Map integration will be added in the next update</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Day-by-day Schedule */}
            <Card>
              <CardHeader>
                <CardTitle>Daily Schedule</CardTitle>
                <CardDescription>
                  Your day-by-day itinerary with activities and timings
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Array.isArray(itinerary?.scheduled_items) && itinerary.scheduled_items.length > 0 ? (
                    itinerary.scheduled_items.map((dayItems: any[], dayIndex: number) => {
                      return (
                        <div key={dayIndex} className="border rounded-lg p-4 bg-white">
                          <div className="flex items-center justify-between gap-4 flex-wrap">
                            <h2 className="text-xl font-semibold">Day {dayIndex + 1}</h2>
                            <div className="space-x-2 flex items-center flex-wrap gap-2">
                              <input
                                type="number"
                                min={1}
                                max={20}
                                placeholder="Max stops"
                                className="w-28 border rounded px-2 py-1 text-sm"
                                value={constraints[dayIndex]?.maxStops ?? ''}
                                onChange={(e) =>
                                  setConstraints((prev) => ({
                                    ...prev,
                                    [dayIndex]: { ...prev[dayIndex], maxStops: e.target.value ? Number(e.target.value) : undefined },
                                  }))
                                }
                              />
                              <input
                                type="number"
                                min={0}
                                placeholder="Max price/activity"
                                className="w-40 border rounded px-2 py-1 text-sm"
                                value={constraints[dayIndex]?.maxPrice ?? ''}
                                onChange={(e) =>
                                  setConstraints((prev) => ({
                                    ...prev,
                                    [dayIndex]: { ...prev[dayIndex], maxPrice: e.target.value ? Number(e.target.value) : undefined },
                                  }))
                                }
                              />
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRegenerateDay(dayIndex)}
                                disabled={regenLoadingDay === dayIndex}
                              >
                                {regenLoadingDay === dayIndex ? 'Regenerating…' : 'Regenerate day'}
                              </Button>
                              <Button size="sm" variant="outline">
                                Add Activity
                              </Button>
                              <Button size="sm" variant="outline">
                                Edit Day
                              </Button>
                            </div>
                          </div>
                          <div className="space-y-2">
                            {Array.isArray(dayItems) && dayItems.length > 0 ? (
                              dayItems.map((activity: any, actIdx: number) => (
                                <div key={activity.id || actIdx} className="bg-gray-50 p-3 rounded-lg">
                                  <div className="flex items-center justify-between">
                                    <div>
                                      <h4 className="font-medium">{activity.name || activity.title || 'Activity'}</h4>
                                      <p className="text-sm text-gray-600">Description: {activity.description}</p>
                                      <p className="text-sm text-gray-600">Location: {activity.location}</p>
                                      <p className="text-sm text-gray-600">Rating: {activity.rating}</p>
                                      <p className="text-sm text-gray-600">Price: $ {activity.price}</p>        
                                      {activity.scheduled_time && (
                                        <p className="text-sm text-gray-600">
                                          {new Date(activity.scheduled_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </p>
                                      )}
                                      {activity.notes && (
                                        <p className="text-xs text-gray-500 mt-1">{activity.notes}</p>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))
                            ) : (
                              <div className="bg-yellow-50 p-3 rounded-lg text-yellow-800">
                                No activities found for this day.
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="bg-yellow-50 p-3 rounded-lg text-yellow-800">
                      No scheduled items found.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Cost Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Cost Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Accommodation</span>
                    <span className="font-medium">${Math.round((itinerary.budget || 1000) * 0.4)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Transportation</span>
                    <span className="font-medium">${Math.round((itinerary.budget || 1000) * 0.3)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Activities</span>
                    <span className="font-medium">${Math.round((itinerary.budget || 1000) * 0.2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Food & Dining</span>
                    <span className="font-medium">${Math.round((itinerary.budget || 1000) * 0.1)}</span>
                  </div>
                  <hr />
                  <div className="flex justify-between font-semibold">
                    <span>Total Budget</span>
                    <span>${itinerary.budget || 'N/A'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Trip Actions */}
            <Card>
              <CardHeader>
                <CardTitle>Trip Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {publicLink && (
                  <div className="text-xs text-gray-600 break-all">Share link: {publicLink}</div>
                )}
                <Button className="w-full" variant="primary" onClick={handleCreateShareLink}>
                  Create Shareable Link
                </Button>
                <Button className="w-full" variant="outline">
                  Export to PDF
                </Button>
                <Button className="w-full" variant="outline">
                  Add to Calendar
                </Button>
                <Button className="w-full" variant="outline">
                  Print Itinerary
                </Button>
              </CardContent>
            </Card>

            {/* Trip Notes */}
            <Card>
              <CardHeader>
                <CardTitle>Trip Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <textarea
                  placeholder="Add your personal notes about this trip..."
                  className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 resize-none text-sm"
                />
                <Button size="sm" className="mt-2">
                  Save Notes
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
