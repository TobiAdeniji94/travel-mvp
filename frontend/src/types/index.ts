/**
 * Type definitions for Travel MVP
 */

export interface User {
  id: string;
  username: string;
  email: string;
  preferences?: any;
  travel_history?: any;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
}

export interface Itinerary {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  destination: string;
  start_date: string;
  end_date: string;
  budget?: number;
  status: 'draft' | 'confirmed' | 'completed' | 'cancelled';
  preferences?: any;
  created_at: string;
  updated_at: string;
  destinations?: ItineraryDestination[];
  activities?: ItineraryActivity[];
  accommodations?: ItineraryAccommodation[];
  transportations?: ItineraryTransportation[];
}

export interface ItineraryDestination {
  id: string;
  itinerary_id: string;
  destination_id: string;
  order: number;
  destination: Destination;
}

export interface ItineraryActivity {
  id: string;
  itinerary_id: string;
  activity_id: string;
  order: number;
  activity: Activity;
}

export interface ItineraryAccommodation {
  id: string;
  itinerary_id: string;
  accommodation_id: string;
  order: number;
  accommodation: Accommodation;
}

export interface ItineraryTransportation {
  id: string;
  itinerary_id: string;
  transportation_id: string;
  order: number;
  transportation: Transportation;
}

export interface Destination {
  id: string;
  name: string;
  description?: string;
  latitude: number;
  longitude: number;
  country: string;
  city: string;
  category?: string;
  rating?: number;
  price_level?: number;
  image_url?: string;
}

export interface Activity {
  id: string;
  name: string;
  description?: string;
  latitude: number;
  longitude: number;
  category: string;
  duration_minutes?: number;
  price?: number;
  rating?: number;
  opening_hours?: string;
  image_url?: string;
}

export interface Accommodation {
  id: string;
  name: string;
  description?: string;
  latitude: number;
  longitude: number;
  type: string;
  price_per_night?: number;
  rating?: number;
  amenities?: string[];
  image_url?: string;
}

export interface Transportation {
  id: string;
  type: string;
  departure_location: string;
  arrival_location: string;
  departure_lat: number;
  departure_long: number;
  arrival_lat: number;
  arrival_long: number;
  departure_time: string;
  arrival_time: string;
  price?: number;
  provider?: string;
}

export interface TravelPreferences {
  interests: string[];
  budget: number;
  travel_style: string[];
  pace: 'relaxed' | 'moderate' | 'intense';
  accommodation_type?: string;
  transportation_preference?: string;
}

export interface NLPParseResult {
  original_text: string;
  parsed_data: {
    destination?: string;
    dates?: string[];
    budget?: number;
    interests?: string[];
    travel_style?: string[];
    duration?: number;
    travelers?: number;
  };
  processing_time: number;
  confidence_score?: number;
  errors: string[];
}

export interface RecommendationRequest {
  interests: string[];
  budget: number;
  limit?: number;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
}

export interface ApiError {
  message: string;
  status: number;
  details?: any;
}
