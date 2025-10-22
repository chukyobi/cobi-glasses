"use client"

import { useRef, useState } from "react"
import { View, StyleSheet, Text, TouchableOpacity, Animated, Dimensions, ScrollView } from "react-native"
import { LinearGradient } from "expo-linear-gradient"

const { width } = Dimensions.get("window")

interface OnboardingSlide {
  id: number
  title: string
  description: string
  icon: string
}

const slides: OnboardingSlide[] = [
  {
    id: 1,
    title: "Welcome to Cobi",
    description: "Your smart companion for seamless connectivity. Connect your glasses to your phone with ease.",
    icon: "👓",
  },
  {
    id: 2,
    title: "Real-time Communication",
    description: "Stay connected with instant transcription and real-time messaging. Never miss a moment.",
    icon: "💬",
  },
  {
    id: 3,
    title: "Your World, Enhanced",
    description: "Experience AI-powered translation and smart modes. Your world, just better.",
    icon: "🧠",
  },
]

export default function OnboardingScreen({ onComplete, onSkip }: { onComplete: () => void; onSkip: () => void }) {
  const [currentSlide, setCurrentSlide] = useState(0)
  const scrollViewRef = useRef<ScrollView>(null)
  const slideProgress = useRef(new Animated.Value(0)).current

  const handleNext = () => {
    if (currentSlide < slides.length - 1) {
      const nextSlide = currentSlide + 1
      setCurrentSlide(nextSlide)
      scrollViewRef.current?.scrollTo({
        x: nextSlide * width,
        animated: true,
      })
    } else {
      onComplete()
    }
  }

  const handleSkip = () => {
    onSkip()
  }

  const handleScroll = (event: any) => {
    const contentOffsetX = event.nativeEvent.contentOffset.x
    const currentIndex = Math.round(contentOffsetX / width)
    setCurrentSlide(currentIndex)
  }

  return (
    <LinearGradient
      colors={["#0f172a", "#1e293b", "#0f172a"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >
      <ScrollView
        ref={scrollViewRef}
        horizontal
        pagingEnabled
        scrollEventThrottle={16}
        onScroll={handleScroll}
        showsHorizontalScrollIndicator={false}
        scrollEnabled={false}
      >
        {slides.map((slide) => (
          <View key={slide.id} style={styles.slide}>
            <View style={styles.iconContainer}>
              <Text style={styles.icon}>{slide.icon}</Text>
            </View>

            <Text style={styles.title}>{slide.title}</Text>
            <Text style={styles.description}>{slide.description}</Text>
          </View>
        ))}
      </ScrollView>

      {/* Slide Indicators */}
      <View style={styles.indicatorContainer}>
        {slides.map((_, index) => (
          <View
            key={index}
            style={[
              styles.indicator,
              {
                backgroundColor: index === currentSlide ? "#3b82f6" : "#475569",
              },
            ]}
          />
        ))}
      </View>

      {/* Action Buttons */}
      <View style={styles.buttonContainer}>
        <TouchableOpacity onPress={handleSkip}>
          <Text style={styles.skipButton}>Skip</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.nextButton} onPress={handleNext}>
          <Text style={styles.nextButtonText}>{currentSlide === slides.length - 1 ? "Get Started" : "Next"}</Text>
        </TouchableOpacity>
      </View>
    </LinearGradient>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "space-between",
    paddingBottom: 40,
  },
  slide: {
    width,
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 30,
  },
  iconContainer: {
    marginBottom: 40,
  },
  icon: {
    fontSize: 80,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: "#ffffff",
    marginBottom: 16,
    textAlign: "center",
  },
  description: {
    fontSize: 16,
    color: "#cbd5e1",
    textAlign: "center",
    lineHeight: 24,
  },
  indicatorContainer: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
    marginBottom: 40,
  },
  indicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  buttonContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
  },
  skipButton: {
    fontSize: 16,
    color: "#cbd5e1",
    fontWeight: "500",
  },
  nextButton: {
    backgroundColor: "#3b82f6",
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius: 8,
  },
  nextButtonText: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
})
