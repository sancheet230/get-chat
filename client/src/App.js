import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './components/LoginPage';
import SignupPage from './components/SignupPage';
import ForgotPasswordPage from './components/ForgotPasswordPage';
import ChatPage from './components/ChatPage';
import ProfilePage from './components/ProfilePage';
import CONFIG from './config';
import './App.css';

function App() {
  const [authToken, setAuthToken] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [showProfile, setShowProfile] = useState(false);
  const [tokenLoaded, setTokenLoaded] = useState(false);

  useEffect(() => {
    // Check if user is already logged in and validate token
    const token = localStorage.getItem('token');
    console.log('Token from localStorage:', token);
    if (token) {
      setAuthToken(token);
    }
    setTokenLoaded(true);
  }, []);

  // Validate token when it changes
  useEffect(() => {
    const validateToken = async () => {
      if (authToken) {
        console.log('Validating token:', authToken);
        try {
          const response = await fetch(`${CONFIG.API_BASE_URL}/api/current-user`, {
            headers: {
              'Authorization': `Bearer ${authToken}`
            }
          });
          
          console.log('Token validation response status:', response.status);
          
          if (!response.ok) {
            if (response.status === 401) {
              // Token is invalid or expired
              console.log('Token is invalid or expired, removing from localStorage');
              localStorage.removeItem('token');
              setAuthToken(null);
              setCurrentUser(null);
            }
          }
        } catch (error) {
          console.error('Token validation error:', error);
          // If there's a network error, we'll assume the token is still valid
          // The user data fetching effect will handle actual errors
        }
      }
    };
    
    if (tokenLoaded) {
      validateToken();
    }
  }, [authToken, tokenLoaded]);

  // Fetch current user data
  useEffect(() => {
    const fetchCurrentUser = async () => {
      console.log('Fetching current user, authToken:', authToken, 'tokenLoaded:', tokenLoaded);
      if (authToken) {
        try {
          const response = await fetch(`${CONFIG.API_BASE_URL}/api/current-user`, {
            headers: {
              'Authorization': `Bearer ${authToken}`
            }
          });
          
          console.log('Fetch current user response status:', response.status);
          
          if (!response.ok) {
            if (response.status === 401) {
              // Token is invalid or expired
              console.log('Token is invalid or expired in fetchCurrentUser, removing from localStorage');
              localStorage.removeItem('token');
              setAuthToken(null);
              setCurrentUser(null);
            }
            return;
          }
          
          const userData = await response.json();
          console.log('Current user data:', userData);
          setCurrentUser(userData);
        } catch (error) {
          console.error('Error fetching current user:', error);
        }
      }
    };
    
    // Only fetch user data when token is loaded
    if (tokenLoaded) {
      fetchCurrentUser();
    }
  }, [authToken, tokenLoaded]);

  const handleSetAuthToken = (token) => {
    setAuthToken(token);
    if (token) {
      localStorage.setItem('token', token);
    }
  };

  const handleLogout = () => {
    setAuthToken(null);
    setCurrentUser(null);
    localStorage.removeItem('token');
  };

  const handleUpdateProfile = (updatedUser) => {
    setCurrentUser(updatedUser);
  };

  const handleShowProfile = () => {
    setShowProfile(true);
  };

  const handleHideProfile = () => {
    setShowProfile(false);
  };

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Navigate to="/login" />} />
          <Route path="/login" element={<LoginPage setAuthToken={handleSetAuthToken} />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route 
            path="/chat" 
            element={(() => {
              console.log('Routing decision - tokenLoaded:', tokenLoaded, 'authToken:', authToken, 'showProfile:', showProfile);
              return tokenLoaded && authToken ? (
                showProfile ? (
                  <ProfilePage 
                    authToken={authToken} 
                    currentUser={currentUser} 
                    onUpdateProfile={handleUpdateProfile} 
                    onBack={handleHideProfile} 
                  />
                ) : (
                  <ChatPage 
                    authToken={authToken} 
                    currentUser={currentUser} 
                    onLogout={handleLogout} 
                    onShowProfile={handleShowProfile} 
                  />
                )
              ) : tokenLoaded ? (
                <Navigate to="/login" />
              ) : (
                // Show a loading state while checking token
                <div>Loading...</div>
              );
            })()} 
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;