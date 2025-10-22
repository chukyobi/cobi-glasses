"use client"

import { Stack } from "expo-router"
import { useEffect } from "react"
import * as SplashScreen from "expo-splash-screen"

SplashScreen.preventAutoHideAsync()

export default function RootLayout() {
  useEffect(() => {
    const timer = setTimeout(() => {
      SplashScreen.hideAsync()
    }, 3000)

    return () => clearTimeout(timer)
  }, [])

  return (
    <Stack initialRouteName="splash">
      <Stack.Screen
        name="splash"
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="onboarding"
        options={{
          headerShown: false,
        }}
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
  )
}
