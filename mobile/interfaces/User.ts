// the user object
export interface User {
    id: string;
    name: string;
    email: string;
    isOnboarded: boolean; 
    // Add other user fields here
  }
  
  // related types
  export interface SignInCredentials {
      email: string;
      password: string;
  }