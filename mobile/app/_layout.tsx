import { Stack, router, usePathname } from 'expo-router';
import React, { useEffect } from 'react'; 
import { useAuthStore } from '@/stores/useAuthStore';
import SplashScreenView from '@/screens/SplashScreen'; 

export default function RootLayout() {
  // Use isHydrated as the single source of truth for session restoration status
  const { token, restoreSession, isHydrated } = useAuthStore();
  
  const currentPath = usePathname();

  // SESSION RESTORATION
  // Call restoreSession once on mount. isHydrated will be set to true by the store when complete.
  useEffect(() => {
    // The dependency array only contains restoreSession, ensuring this runs only on mount.
    restoreSession(); 
  }, [restoreSession]);


  // AUTHENTICATION GATE
  // Navigates only when the session check is complete (isHydrated is true)
  useEffect(() => {
    // isHydrated means the restoreSession call has finished
    if (isHydrated) {
      const destination = token ? '/(tabs)' : '/(auth)';
      
      // Crucial fix: Prevent navigation if we are already on the correct route
      if (!currentPath.startsWith(destination)) {
        router.replace(destination);
      }
    }
  }, [isHydrated, token, currentPath]); 
  // We now rely solely on 'isHydrated' from the store.

  // LOADING/SPLASH SCREEN GATE 
  // This ensures we show the custom splash UI while the session is being restored.
  // Use isHydrated as the loading gate.
  if (!isHydrated) {
    return <SplashScreenView />;
  }

  // ROOT NAVIGATOR (Renders ONLY after the auth status is known)
  return (
    <Stack>
      {/* The splash screen can be safely omitted/ignored from the Stack when the 
          splash screen component is returned above. */}
      <Stack.Screen name="splash" options={{ headerShown: false }} /> 
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
    </Stack>
  );
}
