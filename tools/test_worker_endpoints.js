/**
 * Tests for airport API worker endpoints
 * Run with: npm test tools/test_worker_endpoints.js
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';

// Mock Cloudflare fetch globally for testing
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock caches API
global.caches = {
  default: {
    match: jest.fn(),
    put: jest.fn(),
  },
};

// Import worker logic
import worker from '../worker/airport-api.js';

describe('Airport API Worker', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    global.caches.default.match.mockClear();
    global.caches.default.put.mockClear();
  });

  it('should return 404 for invalid routes', async () => {
    const request = new Request('http://localhost/invalid', { method: 'GET' });
    const response = await worker.fetch(request);
    expect(response.status).toBe(404);
  });

  describe('Weather endpoint', () => {
    it('should return JSON with metar field for valid airport', async () => {
      // Mock aviationweather.gov response
      mockFetch.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            results: [
              {
                raw_text: 'KJFK 121851Z 31008KT 10SM FEW250 23/14 A3012',
              },
            ],
          }),
          { status: 200 }
        )
      );

      global.caches.default.match.mockResolvedValueOnce(null); // Cache miss

      const request = new Request('http://localhost/api/airport/KJFK/weather', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.ident).toBe('KJFK');
      expect(data.metar).toBeDefined();
      expect(data.timestamp).toBeDefined();
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
    });

    it('should handle 3-letter airport codes (JFK -> KJFK)', async () => {
      mockFetch.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            results: [
              {
                raw_text: 'KJFK 121851Z 31008KT 10SM FEW250 23/14 A3012',
              },
            ],
          }),
          { status: 200 }
        )
      );

      global.caches.default.match.mockResolvedValueOnce(null);

      const request = new Request('http://localhost/api/airport/JFK/weather', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.ident).toBe('JFK');
    });

    it('should return error on timeout', async () => {
      mockFetch.mockImplementationOnce(() => {
        throw new Error('AbortError: The operation was aborted.');
      });

      global.caches.default.match.mockResolvedValueOnce(null);

      const request = new Request('http://localhost/api/airport/KJFK/weather', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(503);
      const data = await response.json();
      expect(data.error).toBeDefined();
      expect(data.timestamp).toBeDefined();
    });

    it('should cache weather responses', async () => {
      mockFetch.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            results: [
              {
                raw_text: 'KJFK 121851Z 31008KT 10SM FEW250 23/14 A3012',
              },
            ],
          }),
          { status: 200 }
        )
      );

      global.caches.default.match.mockResolvedValueOnce(null);

      const request = new Request('http://localhost/api/airport/KJFK/weather', {
        method: 'GET',
      });
      await worker.fetch(request);

      expect(global.caches.default.put).toHaveBeenCalled();
    });
  });

  describe('NOTAMs endpoint', () => {
    it('should return JSON with empty notams array', async () => {
      const request = new Request('http://localhost/api/airport/KJFK/notams', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.ident).toBe('KJFK');
      expect(Array.isArray(data.notams)).toBe(true);
      expect(data.timestamp).toBeDefined();
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
    });
  });

  describe('Airspace endpoint', () => {
    it('should return JSON with airspace class', async () => {
      const request = new Request('http://localhost/api/airport/KJFK/airspace', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.ident).toBe('KJFK');
      expect(data.airspace_class).toBeDefined();
      expect(Array.isArray(data.moas)).toBe(true);
      expect(data.timestamp).toBeDefined();
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
    });
  });

  describe('Fuel endpoint', () => {
    it('should return JSON with fuel types', async () => {
      const request = new Request('http://localhost/api/airport/KJFK/fuel', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.ident).toBe('KJFK');
      expect(Array.isArray(data.fuel_types)).toBe(true);
      expect(data.timestamp).toBeDefined();
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
    });
  });

  describe('CORS headers', () => {
    it('should set correct CORS headers on all endpoints', async () => {
      const endpoints = ['weather', 'notams', 'airspace', 'fuel'];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost/api/airport/KJFK/${endpoint}`, {
          method: 'GET',
        });
        const response = await worker.fetch(request);

        expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
        expect(response.headers.get('Content-Type')).toMatch(/application\/json/);
      }
    });
  });

  describe('Invalid airport codes', () => {
    it('should return 404 for invalid airport code format', async () => {
      const request = new Request('http://localhost/api/airport/K/weather', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(404);
    });

    it('should return 404 for code with special characters', async () => {
      const request = new Request('http://localhost/api/airport/KJ%21FK/weather', {
        method: 'GET',
      });
      const response = await worker.fetch(request);

      expect(response.status).toBe(404);
    });
  });
});
