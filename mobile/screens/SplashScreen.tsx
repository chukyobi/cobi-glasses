"use client"

import { useEffect, useRef } from "react"
import { View, StyleSheet, Animated, Text } from "react-native"
import { LinearGradient } from "expo-linear-gradient"

export default function SplashScreen() {
  const dot1Opacity = useRef(new Animated.Value(0.3)).current
  const dot2Opacity = useRef(new Animated.Value(0.3)).current
  const dot3Opacity = useRef(new Animated.Value(0.3)).current

  useEffect(() => {
    const createPulseAnimation = (animatedValue: Animated.Value) => {
      return Animated.loop(
        Animated.sequence([
          Animated.timing(animatedValue, {
            toValue: 1,
            duration: 600,
            useNativeDriver: true,
          }),
          Animated.timing(animatedValue, {
            toValue: 0.3,
            duration: 600,
            useNativeDriver: true,
          }),
        ]),
      )
    }

    const animation1 = createPulseAnimation(dot1Opacity)
    const animation2 = createPulseAnimation(dot2Opacity)
    const animation3 = createPulseAnimation(dot3Opacity)

    // Stagger the animations
    Animated.stagger(200, [animation1, animation2, animation3]).start()

    return () => {
      animation1.stop()
      animation2.stop()
      animation3.stop()
    }
  }, [dot1Opacity, dot2Opacity, dot3Opacity])

  return (
    <LinearGradient
      colors={["#0f172a", "#1e293b", "#0f172a"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >
      <View style={styles.content}>
        {/* Logo Section */}
        <View style={styles.logoContainer}>
          <Text style={styles.logo}>Cobi</Text>
          <Text style={styles.tagline}>Companion App</Text>
        </View>

        {/* Loading Indicator */}
        <View style={styles.loadingContainer}>
          <View style={styles.dotsContainer}>
            <Animated.View
              style={[
                styles.dot,
                {
                  opacity: dot1Opacity,
                },
              ]}
            />
            <Animated.View
              style={[
                styles.dot,
                {
                  opacity: dot2Opacity,
                },
              ]}
            />
            <Animated.View
              style={[
                styles.dot,
                {
                  opacity: dot3Opacity,
                },
              ]}
            />
          </View>
        </View>
      </View>
    </LinearGradient>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  content: {
    flex: 1,
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 100,
  },
  logoContainer: {
    alignItems: "center",
    marginTop: 80,
  },
  logo: {
    fontSize: 64,
    fontWeight: "700",
    color: "#ffffff",
    letterSpacing: 2,
    fontFamily: "System",
  },
  tagline: {
    fontSize: 14,
    color: "#94a3b8",
    marginTop: 12,
    letterSpacing: 1,
    fontFamily: "System",
  },
  loadingContainer: {
    marginBottom: 60,
    alignItems: "center",
  },
  dotsContainer: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#3b82f6",
  },
})
