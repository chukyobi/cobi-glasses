import { Stack } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { useAuthStore } from '@/stores/useAuthStore';
import SplashScreenView from '@/screens/SplashScreen'; // Reusable splash component

export default function RootLayout() {
  const { token, isLoading: authLoading, restoreSession } = useAuthStore();
  const [isReady, setIsReady] = useState(false);

  // On mount, restore session
  useEffect(() => {
    const init = async () => {
      await restoreSession();
      setIsReady(true);
    };
    init();
  }, [restoreSession]);

  // If not ready yet, show splash
  if (!isReady) {
    // On mobile we can optionally keep expo-splash-screen logic
    return <SplashScreenView />;
  }

  return (
    <Stack>
      <Stack.Screen name="splash" options={{ headerShown: false }} />

      {/* Auth routes */}
      <Stack.Screen
        name="(auth)"
        options={{ headerShown: false }}
      />

      {/* Main app tabs */}
      <Stack.Screen
        name="(tabs)"
        options={{ headerShown: false }}
      />
    </Stack>
  );
}
