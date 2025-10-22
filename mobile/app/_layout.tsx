import { Stack, Redirect, useRouter } from 'expo-router';
import React, { useEffect, useState } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useAuthStore } from '@/stores/useAuthStore'; 

// This prevents the splash screen from hiding automatically while we check auth status.
SplashScreen.preventAutoHideAsync();

// The visual component to display while the stores are checking
// function LoadingSplash() {
//   return (
//     <View style={styles.container}>
//       <ActivityIndicator size="large" color="#3b82f6" /> 
//     </View>
//   );
// }

// --- Root Layout Logic (The Brains) ---
// This component handles the async check and routing decision.
function InitialRouteResolver() {
  const router = useRouter();
  // Destructure all needed state and actions from the store
  const { token, isLoading: authLoading, restoreSession } = useAuthStore(); 
  
  const [isReady, setIsReady] = useState(false);
  
  // Combine all loading states (currently just authLoading)
  const isEverythingLoading = authLoading; 

  // Check session status on component mount
  useEffect(() => {
    // Only call restoreSession if we haven't already finished the loading process
    if (!isReady) {
      restoreSession(); 
    }
  }, [restoreSession, isReady]); 

  // Handle Navigation when loading is complete
  useEffect(() => {
    
    // Check if the loading has finished AND we aren't already ready
    if (!isEverythingLoading && !isReady) {
      SplashScreen.hideAsync(); 
      setIsReady(true);
      
      // --- Deep Link Decision Tree ---
      if (token) {
        // User has a token (is logged in)
        router.replace('/(tabs)');
      } else {
        // User has no token (is not logged in)
        router.replace('/(auth)/login');
      }
    }
  }, [isEverythingLoading, token, router, isReady]);

  // If we're still checking, show the splash screen
  // if (!isReady) {
  //   return <LoadingSplash />;
  // }

  // Once ready, render the full application stack
  return (
    <Stack>
      <Stack.Screen
        name="splash" 
        options={{ headerShown: false }}
      />
     
      <Stack.Screen
        name="(auth)"
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="(tabs)"
        options={{
          headerShown: false,
        }}
      />
    </Stack>
  );
}


// --- Main Export for Expo Router ---
// Expo Router REQUIRES the default export of _layout.tsx to be the component 
// that renders the Stack/Tabs, which is now our InitialRouteResolver.
export default function RootLayout() {
  return <InitialRouteResolver />;
}


const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0f172a', 
  },
});
