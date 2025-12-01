import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './ProfilePage.css';

const ProfilePage = ({ authToken, currentUser, onUpdateProfile, onBack }) => {
  const [username, setUsername] = useState('');
  const [profilePicture, setProfilePicture] = useState('');
  const [previewImage, setPreviewImage] = useState('');
  const [securityCodes, setSecurityCodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (currentUser) {
      setUsername(currentUser.username || '');
      setProfilePicture(currentUser.profile_picture || '');
      setPreviewImage(currentUser.profile_picture || '');
      
      // Fetch security codes
      if (currentUser.email) {
        fetch(`http://localhost:8000/api/security-codes/${currentUser.email}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        })
        .then(response => {
          if (response.ok) {
            return response.json();
          }
          throw new Error('Failed to fetch security codes');
        })
        .then(data => {
          setSecurityCodes(data.security_codes || []);
        })
        .catch(err => {
          console.error('Error fetching security codes:', err);
        });
      }
    }
  }, [currentUser, authToken]);

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setProfilePicture(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviewImage(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess(false);

    try {
      // Handle profile picture upload if a new file is selected
      let profilePictureUrl = currentUser?.profile_picture;
      
      if (profilePicture && typeof profilePicture !== 'string') {
        try {
          // Upload the new profile picture to Cloudinary
          const formData = new FormData();
          formData.append('file', profilePicture);
          
          console.log('Uploading profile picture...');
          
          const uploadResponse = await fetch('http://localhost:8000/api/upload-profile-picture', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${authToken}`
            },
            body: formData
          });
          
          console.log('Upload response status:', uploadResponse.status);
          
          if (uploadResponse.status === 401) {
            // Token expired
            localStorage.removeItem('token');
            navigate('/login');
            return;
          }
          
          const uploadData = await uploadResponse.json();
          console.log('Upload response data:', uploadData);
          
          if (uploadResponse.ok) {
            profilePictureUrl = uploadData.url;
            console.log('Profile picture uploaded successfully:', profilePictureUrl);
          } else {
            console.error('Upload failed:', uploadData);
            throw new Error(uploadData.detail || 'Failed to upload profile picture');
          }
        } catch (uploadError) {
          console.error('Error during profile picture upload:', uploadError);
          throw new Error(`Failed to upload profile picture: ${uploadError.message}`);
        }
      }
      
      // Update profile with username and profile picture URL
      console.log('Updating profile with:', {
        username: username !== currentUser?.username ? username : undefined,
        profile_picture: profilePictureUrl !== currentUser?.profile_picture ? profilePictureUrl : undefined
      });
      
      const response = await fetch('http://localhost:8000/api/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          username: username !== currentUser?.username ? username : undefined,
          profile_picture: profilePictureUrl !== currentUser?.profile_picture ? profilePictureUrl : undefined
        })
      });

      console.log('Profile update response status:', response.status);
      
      if (response.status === 401) {
        // Token expired
        localStorage.removeItem('token');
        navigate('/login');
        return;
      }

      const data = await response.json();
      console.log('Profile update response data:', data);

      if (response.ok) {
        setSuccess(true);
        // Update the current user in the parent component
        if (onUpdateProfile) {
          onUpdateProfile(data);
        }
        // Reset success message after 3 seconds
        setTimeout(() => setSuccess(false), 3000);
      } else {
        setError(data.detail || 'Failed to update profile');
      }
    } catch (err) {
      console.error('Error in handleSubmit:', err);
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        setError('Network error: Unable to connect to the server. Please check your internet connection and try again.');
      } else {
        setError(err.message || 'Network error. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="profile-container">
      <div className="profile-header">
        <button onClick={onBack} className="back-button">← Back</button>
        <h2>Profile Settings</h2>
      </div>
      
      <div className="profile-form">
        {error && <div className="error-message">{error}</div>}
        {success && <div className="success-message">Profile updated successfully!</div>}
        
        <form onSubmit={handleSubmit}>
          <div className="profile-picture-section">
            <div className="profile-picture-preview">
              {previewImage ? (
                <img src={previewImage} alt="Profile" className="profile-image" />
              ) : (
                <div className="profile-placeholder">
                  {username ? username.charAt(0).toUpperCase() : 'U'}
                </div>
              )}
            </div>
            <div className="profile-picture-upload">
              <label htmlFor="profile-picture" className="upload-button">
                Change Profile Picture
              </label>
              <input
                type="file"
                id="profile-picture"
                accept="image/*"
                onChange={handleImageChange}
                style={{ display: 'none' }}
              />
              <p className="upload-hint">Upload a JPG, PNG, or GIF image</p>
            </div>
          </div>
          
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          
          <div className="form-group">
            <label>Security Codes</label>
            <p className="security-codes-hint">Save these codes in a secure place. You'll need them to reset your password.</p>
            <div className="security-codes-list">
              {securityCodes.length > 0 ? (
                securityCodes.map((code, index) => (
                  <div key={index} className="security-code-item">
                    <span className="security-code">{code}</span>
                  </div>
                ))
              ) : (
                <p className="no-codes">No security codes available</p>
              )}
            </div>
          </div>
          
          <div className="form-actions">
            <button type="submit" disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProfilePage;