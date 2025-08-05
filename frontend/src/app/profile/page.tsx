'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Navigation from '@/components/Navigation';

export default function ProfilePage() {
  const { user, isAuthenticated } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  const [profileData, setProfileData] = useState({
    username: '',
    email: '',
  });

  const [preferences, setPreferences] = useState({
    interests: [] as string[],
    budget: 1000,
    travel_style: [] as string[],
    pace: 'moderate' as 'relaxed' | 'moderate' | 'intense',
  });

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }

    if (user) {
      setProfileData({
        username: user.username,
        email: user.email,
      });

      // Set preferences from user data if available
      if (user.preferences) {
        setPreferences({
          interests: user.preferences.interests || [],
          budget: user.preferences.budget || 1000,
          travel_style: user.preferences.travel_style || [],
          pace: user.preferences.pace || 'moderate',
        });
      }
    }
  }, [user, isAuthenticated, router]);

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      // This would update the user profile via API
      // await apiClient.updateUser(user.id, profileData);
      setMessage('Profile updated successfully!');
    } catch (error) {
      setMessage('Failed to update profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handlePreferencesUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      // This would update user preferences via API
      // await apiClient.updateUserPreferences(user.id, preferences);
      setMessage('Preferences updated successfully!');
    } catch (error) {
      setMessage('Failed to update preferences. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated || !user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      
      <main className="max-w-4xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Profile & Settings</h1>
          <p className="mt-2 text-gray-600">
            Manage your account information and travel preferences
          </p>
        </div>

        {message && (
          <div className={`mb-6 p-4 rounded-lg ${
            message.includes('successfully') 
              ? 'bg-green-50 border border-green-200 text-green-700'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            {message}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Profile Information */}
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Update your account details and contact information
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileUpdate} className="space-y-4">
                <Input
                  label="Username"
                  value={profileData.username}
                  onChange={(e) => setProfileData(prev => ({ ...prev, username: e.target.value }))}
                  disabled // Username typically can't be changed
                  helperText="Username cannot be changed"
                />

                <Input
                  label="Email"
                  type="email"
                  value={profileData.email}
                  onChange={(e) => setProfileData(prev => ({ ...prev, email: e.target.value }))}
                />

                <Button
                  type="submit"
                  loading={loading}
                  className="w-full"
                >
                  Update Profile
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Travel Preferences */}
          <Card>
            <CardHeader>
              <CardTitle>Travel Preferences</CardTitle>
              <CardDescription>
                Set your default preferences for trip planning
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePreferencesUpdate} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Default Budget (USD)
                  </label>
                  <Input
                    type="number"
                    value={preferences.budget}
                    onChange={(e) => setPreferences(prev => ({ ...prev, budget: Number(e.target.value) }))}
                    min="0"
                    step="100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Preferred Travel Pace
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['relaxed', 'moderate', 'intense'] as const).map((pace) => (
                      <button
                        key={pace}
                        type="button"
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
                        type="button"
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

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Travel Style
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {['budget', 'mid-range', 'luxury', 'backpacking', 'family', 'business', 'solo', 'group'].map((style) => (
                      <button
                        key={style}
                        type="button"
                        onClick={() => {
                          setPreferences(prev => ({
                            ...prev,
                            travel_style: prev.travel_style.includes(style)
                              ? prev.travel_style.filter(s => s !== style)
                              : [...prev.travel_style, style]
                          }));
                        }}
                        className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                          preferences.travel_style.includes(style)
                            ? 'border-blue-500 bg-blue-50 text-blue-700'
                            : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        {style}
                      </button>
                    ))}
                  </div>
                </div>

                <Button
                  type="submit"
                  loading={loading}
                  className="w-full"
                >
                  Save Preferences
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Account Actions */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>Account Actions</CardTitle>
            <CardDescription>
              Manage your account settings and data
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Button variant="outline" className="w-full">
                Change Password
              </Button>
              <Button variant="outline" className="w-full">
                Export Data
              </Button>
              <Button variant="destructive" className="w-full">
                Delete Account
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
