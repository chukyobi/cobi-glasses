import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { User } from '@/interfaces/User';

// 🔹 Replace this with your ngrok backend URL
const API_URL = 'https://cb9f3396e16d.ngrok-free.app/api/users';
const TOKEN_KEY = 'userToken';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isHydrated: boolean;

  // Now signIn accepts User + token
  signIn: (userData: User, tokenValue: string) => Promise<void>;
  signOut: () => Promise<void>;
  restoreSession: () => Promise<void>;
  markUserOnboarded: () => void;
}


export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: false,
  isHydrated: false,

  // --- 🔑 SIGN IN (CALL BACKEND & STORE TOKEN) ---
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

      // Save token securely
      await SecureStore.setItemAsync(TOKEN_KEY, token);

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

  // --- 🚪 SIGN OUT (CLEAR TOKEN & STATE) ---
  signOut: async () => {
    try {
      set({ isLoading: true });
      await SecureStore.deleteItemAsync(TOKEN_KEY);
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

  // --- ♻️ RESTORE SESSION (ON APP LAUNCH) ---
  restoreSession: async () => {
    try {
      set({ isLoading: true });

      const savedToken = await SecureStore.getItemAsync(TOKEN_KEY);

      if (!savedToken) {
        set({ user: null, token: null, isLoading: false, isHydrated: true });
        return;
      }

      // Validate token with backend
      const response = await fetch(`${API_URL}/me`, {
        headers: { Authorization: `Bearer ${savedToken}` },
      });

      if (!response.ok) {
        await SecureStore.deleteItemAsync(TOKEN_KEY);
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

  // --- ✅ MARK USER AS ONBOARDED LOCALLY ---
  markUserOnboarded: () => {
    const { user } = get();
    if (user) {
      set({
        user: { ...user, isOnboarded: true },
      });
    }
  },
}));
