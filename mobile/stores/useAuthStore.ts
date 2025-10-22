import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import {User} from "@/interfaces/User"


const TOKEN_KEY = 'userToken';


// Define AuthStore interface (State + Actions)
interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  
  signIn: (
    userData: { id: string; name: string; email: string; isOnboarded: boolean }, 
    tokenValue: string
  ) => Promise<void>;
  signOut: () => Promise<void>;
  restoreSession: () => Promise<void>;
  markUserOnboarded: () => void; 
}

export const useAuthStore = create<AuthState>((set) => ({
  // initialiaztion of store state
  user: null,         
  token: null,        
  isLoading: true,    

  signIn: async (userData, tokenValue) => {
    // This assumes userData already contains the isOnboarded status from the server
    await SecureStore.setItemAsync(TOKEN_KEY, tokenValue);
    set({ 
      user: userData, 
      token: tokenValue, 
      isLoading: false 
    });
  },

  signOut: async () => {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    set({
      user: null,
      token: null,
      isLoading: false
    });
  },

  restoreSession: async () => {
    set({ isLoading: true });
    const savedToken = await SecureStore.getItemAsync(TOKEN_KEY);

    if (savedToken) {
      // In a real app, you would fetch the user object (including isOnboarded status)
      // here using the token. For this example, we just restore the token state.
      set({
        user: null, // User details need to be fetched post-restore for full state
        token: savedToken,
        isLoading: false,
      });
    } else {
      set({
        user: null,
        token: null,
        isLoading: false,
      });
    }
  },
  
  // Action to update the user state after onboarding is completed on the client
  markUserOnboarded: () => {
    set((state) => {
      // Safely update the user object if it exists
      if (state.user) {
        return {
          user: {
            ...state.user,
            isOnboarded: true,
          },
        };
      }
      return state;
    });
  }
}));
