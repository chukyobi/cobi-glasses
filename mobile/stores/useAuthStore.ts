import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native'; // Import Platform for environment detection
import { User } from '@/interfaces/User';
import { AppConfig } from '@/config/appConfig'; 

// Pull configuration variables from the centralized file
const API_URL = AppConfig.API_URL;
const TOKEN_KEY = AppConfig.TOKEN_KEY;

// --- Storage Service Implementation for Cross-Platform use ---
const StorageService = {
  // Uses localStorage for web, SecureStore for native (iOS/Android)
  getItem: async (key: string): Promise<string | null> => {
    if (Platform.OS === 'web') {
      try {
        // Use localStorage on the web, wrapped in try/catch for security errors
        return localStorage.getItem(key);
      } catch (e) {
        console.error('LocalStorage getItem error (possible security restriction):', e);
        return null; // Return null if localStorage access fails
      }
    }
    // Use SecureStore for native platforms
    return SecureStore.getItemAsync(key); 
  },
  setItem: async (key: string, value: string): Promise<void> => {
    if (Platform.OS === 'web') {
      try {
        // Use localStorage on the web, wrapped in try/catch for security errors
        localStorage.setItem(key, value);
      } catch (e) {
        console.error('LocalStorage setItem error (possible security restriction):', e);
      }
      return;
    }
    await SecureStore.setItemAsync(key, value);
  },
  deleteItem: async (key: string): Promise<void> => {
    if (Platform.OS === 'web') {
      try {
        // Use localStorage on the web, wrapped in try/catch for security errors
        localStorage.removeItem(key);
      } catch (e) {
        console.error('LocalStorage deleteItem error (possible security restriction):', e);
      }
      return;
    }
    await SecureStore.deleteItemAsync(key);
  },
};
// --- End Storage Service ---


interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isHydrated: boolean;

  signIn: (email: string, password: string) => Promise<void>;
  signUp: (fullName: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  restoreSession: () => Promise<void>;
  markUserOnboarded: () => void;
}


export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: false,
  isHydrated: false,

  // --- SIGN IN (CALL BACKEND & STORE TOKEN) ---
  signIn: async (email, password) => {
    try {
      set({ isLoading: true });

      const response = await fetch(`${API_URL}/login`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Login failed');
      }

      const data = await response.json();
      const { token, user } = data;

      // *** CHANGE: Use StorageService for cross-platform support ***
      await StorageService.setItem(TOKEN_KEY, token); 

      // Update store
      set({
        user,
        token,
        isLoading: false,
        isHydrated: true,
      });
    } catch (error) {
      console.error('❌ SignIn Error:', error);
      set({ isLoading: false });
      throw error;
    }
  },

  // --- SIGN UP (CREATE USER & AUTO-LOGIN) ---
  signUp: async (fullName, email, password) => {
    try {
      set({ isLoading: true });

      const response = await fetch(`${API_URL}/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          name: fullName,
          email, 
          password 
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Sign up failed');
      }

      const user = await response.json();

      // After successful signup, automatically sign in
      await get().signIn(email, password);
    } catch (error) {
      console.error('❌ SignUp Error:', error);
      set({ isLoading: false });
      throw error;
    }
  },

  // --- SIGN OUT (CLEAR TOKEN & STATE) ---
  signOut: async () => {
    try {
      set({ isLoading: true });
      // *** CHANGE: Use StorageService for cross-platform support ***
      await StorageService.deleteItem(TOKEN_KEY); 
    } catch (error) {
      console.error('❌ SignOut Error:', error);
    } finally {
      set({
        user: null,
        token: null,
        isLoading: false,
        isHydrated: true,
      });
    }
  },

  // --- RESTORE SESSION (ON APP LAUNCH) ---
  restoreSession: async () => {
    try {
      set({ isLoading: true });

      // *** CHANGE: Use StorageService for cross-platform support ***
      const savedToken = await StorageService.getItem(TOKEN_KEY); 

      if (!savedToken) {
        set({ user: null, token: null, isLoading: false, isHydrated: true });
        return;
      }

      const response = await fetch(`${API_URL}/me`, { 
        headers: { Authorization: `Bearer ${savedToken}` },
      });

      if (!response.ok) {
        // *** CHANGE: Use StorageService for cross-platform support ***
        await StorageService.deleteItem(TOKEN_KEY);
        set({ user: null, token: null, isLoading: false, isHydrated: true });
        return;
      }

      const userData: User = await response.json();

      set({
        user: userData,
        token: savedToken,
        isLoading: false,
        isHydrated: true,
      });
    } catch (error) {
      console.error('❌ RestoreSession Error:', error);
      set({ user: null, token: null, isLoading: false, isHydrated: true });
    }
  },

  // --- MARK USER AS ONBOARDED LOCALLY ---
  markUserOnboarded: () => {
    const { user } = get();
    if (user) {
      set({
        user: { ...user, isOnboarded: true },
      });
    }
  },
}));
