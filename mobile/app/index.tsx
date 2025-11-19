import { Redirect } from 'expo-router';
import React from 'react';

// This file is the default entry point for the root '/' route.
// We immediately redirect the user to the splash screen or the 
// authentication flow, as the RootLayout handles the main logic.
export default function RootIndex() {
  // The RootLayout will immediately determine the correct route (auth or tabs).
  // We use Redirect here only to ensure the router system does not throw 
  // the "Unmatched RoutePage" error on the initial load attempt.
  // The logic in _layout.tsx ultimately takes precedence.
  return <Redirect href="/splash" />;
}
