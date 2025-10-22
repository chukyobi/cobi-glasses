"use client"

import { useRouter } from "expo-router"
import OnboardingScreen from "@/screens/OnboardingScreen"

export default function OnboardingRoute() {
  const router = useRouter()

  const handleOnboardingComplete = () => {
    router.replace("/(auth)/login")
  }

  const handleSkip = () => {
    router.replace("/(tabs)")
  }

  return <OnboardingScreen onComplete={handleOnboardingComplete} onSkip={handleSkip} />
}

