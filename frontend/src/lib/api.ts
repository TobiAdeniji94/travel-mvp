/**
 * API client for Travel MVP backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    // Initialize token from localStorage if available
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('auth_token');
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('auth_token', token);
      } else {
        localStorage.removeItem('auth_token');
      }
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = new Headers(options.headers);

    // Only set Content-Type if not explicitly provided and body is not FormData
    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        errorData.detail || `HTTP ${response.status}`,
        response.status,
        errorData
      );
    }

    return response.json();
  }

  // Auth endpoints
  async login(username: string, password: string) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    return this.request<{
      access_token: string;
      token_type: string;
      expires_in: number;
    }>('/auth/login', {
      method: 'POST',
      body: formData,
      headers: {}, // Remove Content-Type to let browser set it for FormData
    });
  }

  async register(userData: {
    username: string;
    email: string;
    password: string;
  }) {
    return this.request<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async getCurrentUser() {
    return this.request<any>('/auth/me');
  }

  async logout() {
    return this.request<{ message: string }>('/auth/logout', {
      method: 'POST',
    });
  }

  // Itinerary endpoints
  async createItinerary(data: {
    text: string;
    preferences?: any;
  }) {
    return this.request<any>('/itineraries/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getItineraries() {
    return this.request<any[]>('/itineraries/');
  }

  async getItinerary(id: string) {
    return this.request<any>(`/itineraries/${id}`);
  }

  async updateItinerary(id: string, data: any) {
    return this.request<any>(`/itineraries/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteItinerary(id: string) {
    return this.request<{ message: string }>(`/itineraries/${id}`, {
      method: 'DELETE',
    });
  }

  // NLP endpoints
  async parseTravel(text: string) {
    return this.request<{
      original_text: string;
      parsed_data: any;
      processing_time: number;
      confidence_score?: number;
      errors: string[];
    }>('/nlp/parse', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  // Recommendation endpoints
  async getRecommendations(type: 'destinations' | 'activities' | 'accommodations' | 'transportations', data: {
    interests: string[];
    budget: number;
    limit?: number;
  }) {
    return this.request<any[]>(`/recommend/${type}`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
