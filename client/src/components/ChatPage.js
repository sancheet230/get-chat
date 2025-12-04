import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import CONFIG from '../config';
import './ChatPage.css';

const ChatPage = ({ authToken, currentUser, onLogout, onShowProfile }) => {
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [messages, setMessages] = useState([]);
  const [groupMessages, setGroupMessages] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [showInvitations, setShowInvitations] = useState(false);
  const [showGroupSettings, setShowGroupSettings] = useState(false);
  const [groupName, setGroupName] = useState('');
  const [groupMembers, setGroupMembers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [websocket, setWebsocket] = useState(null);
  const [unreadCounts, setUnreadCounts] = useState({});
  const [groupUnreadCounts, setGroupUnreadCounts] = useState({});
  const [editingGroup, setEditingGroup] = useState(null);
  const [groupProfilePicture, setGroupProfilePicture] = useState(null);
  const [groupProfilePreview, setGroupProfilePreview] = useState('');
  
  // Request notification permission on component mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  // Filter users based on search term
  const filteredUsers = users.filter(user =>
    user.username.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Fetch users and groups when authToken becomes available
  useEffect(() => {
    const fetchUsersAndGroups = async () => {
      console.log('Fetching users and groups with auth token:', authToken ? `${authToken.substring(0, 10)}...` : 'None');
      if (!authToken) {
        console.log('No auth token, returning');
        return;
      }
      
      try {
        // Test server connectivity
        console.log('Testing server connectivity...');
        try {
          const healthResponse = await fetch(`${CONFIG.API_BASE_URL}/health`);
          console.log('Health check response status:', healthResponse.status);
          if (healthResponse.ok) {
            const healthData = await healthResponse.json();
            console.log('Server health:', healthData);
          }
        } catch (healthError) {
          console.error('Health check failed:', healthError);
        }
        
        // Test group endpoint
        console.log('Testing group endpoint...');
        try {
          const testResponse = await fetch(`${CONFIG.API_BASE_URL}/api/test-group`, {
            method: 'POST'
          });
          console.log('Test group endpoint response status:', testResponse.status);
          if (testResponse.ok) {
            const testData = await testResponse.json();
            console.log('Test group endpoint response:', testData);
          }
        } catch (testError) {
          console.error('Test group endpoint failed:', testError);
        }
        
        // Fetch users
        console.log('Fetching users...');
        const usersResponse = await fetch(`${CONFIG.API_BASE_URL}/api/users`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        
        console.log('Users response status:', usersResponse.status);
        
        if (usersResponse.status === 401) {
          console.log('Users fetch unauthorized, logging out');
          handleLogout();
          return;
        }
        
        const usersData = await usersResponse.json();
        console.log('Users data:', usersData);
        setUsers(usersData);
        
        // Fetch groups
        console.log('Fetching groups...');
        const groupsResponse = await fetch(`${CONFIG.API_BASE_URL}/api/groups`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        
        console.log('Groups response status:', groupsResponse.status);
        
        if (groupsResponse.status === 401) {
          console.log('Groups fetch unauthorized, logging out');
          handleLogout();
          return;
        }
        
        const groupsData = await groupsResponse.json();
        console.log('Raw groups data:', groupsData);
        console.log('Type of groups data:', typeof groupsData);
        // Ensure groupsData is an array
        if (Array.isArray(groupsData)) {
          console.log('Setting groups:', groupsData);
          setGroups(groupsData);
        } else {
          console.warn('Groups data is not an array:', groupsData);
          setGroups([]);
        }
        
        // Fetch group invitations
        console.log('Fetching group invitations...');
        const invitationsResponse = await fetch(`${CONFIG.API_BASE_URL}/api/group-invitations`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        
        console.log('Invitations response status:', invitationsResponse.status);
        
        if (invitationsResponse.status === 401) {
          console.log('Invitations fetch unauthorized, logging out');
          handleLogout();
          return;
        }
        
        if (invitationsResponse.ok) {
          const invitationsData = await invitationsResponse.json();
          console.log('Invitations data:', invitationsData);
          setInvitations(invitationsData);
        }
      } catch (error) {
        console.error('Error fetching users and groups:', error);
      }
    };
    
    fetchUsersAndGroups();
    
    // Set up interval to periodically fetch users and groups
    const interval = setInterval(fetchUsersAndGroups, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  // Setup WebSocket connection
  useEffect(() => {
    if (!authToken) return;
    
    const ws = new WebSocket(CONFIG.WEBSOCKET_URL);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      // Send authentication message
      ws.send(JSON.stringify({
        type: 'authenticate',
        token: authToken
      }));
      setWebsocket(ws);
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('WebSocket message received:', data);
      
      if (data.type === 'message') {
        // Add new message to the messages array
        const newMsg = {
          id: data.id || Date.now().toString(),
          sender_id: data.sender_id,
          receiver_id: data.receiver_id,
          content: data.content,
          timestamp: new Date(data.timestamp),
          is_read: data.is_read || false
        };
        
        // Add media fields if present
        if (data.media_url) {
          newMsg.media_url = data.media_url;
          newMsg.media_type = data.media_type;
        };
        
        console.log('Adding message to state:', newMsg);
        
        // Add message to state
        setMessages(prevMessages => {
          // Check if message already exists (avoid duplicates)
          const exists = prevMessages.some(msg => msg.id === newMsg.id);
          if (exists) {
            console.log('Message already exists, skipping');
            return prevMessages;
          }
          
          console.log('Adding new message to state');
          return [...prevMessages, newMsg];
        });
        
        // Only update unread counts if current user is the RECEIVER of this message
        if (data.receiver_id === currentUser?.id && data.sender_id !== currentUser?.id) {
          setUsers(prevUsers => {
            // Move sender to top of list
            const updatedUsers = [...prevUsers];
            const senderIndex = updatedUsers.findIndex(u => u.id === data.sender_id);
            if (senderIndex !== -1) {
              const [sender] = updatedUsers.splice(senderIndex, 1);
              updatedUsers.unshift(sender);
            }
            return updatedUsers;
          });
          
          // Update unread count only if not viewing this conversation
          if (!selectedUser || selectedUser.id !== data.sender_id) {
            setUnreadCounts(prevCounts => ({
              ...prevCounts,
              [data.sender_id]: (prevCounts[data.sender_id] || 0) + 1
            }));
          }
        }
      } else if (data.type === 'group_message') {
        // Handle group message
        const newMsg = {
          id: data.id || Date.now().toString(),
          group_id: data.group_id,
          sender_id: data.sender_id,
          content: data.content,
          timestamp: new Date(data.timestamp),
          is_read: data.is_read || false
        };
        
        // Add media fields if present
        if (data.media_url) {
          newMsg.media_url = data.media_url;
          newMsg.media_type = data.media_type;
        }
        
        console.log('Adding group message to state:', newMsg);
        
        // Add message to group messages state
        setGroupMessages(prevMessages => {
          // Check if message already exists (avoid duplicates)
          const exists = prevMessages.some(msg => msg.id === newMsg.id);
          if (exists) {
            console.log('Group message already exists, skipping');
            return prevMessages;
          }
          
          console.log('Adding new group message to state');
          return [...prevMessages, newMsg];
        });
        
        // Update unread count for group only if not viewing this group
        if (data.sender_id !== currentUser?.id && (!selectedGroup || selectedGroup.id !== data.group_id)) {
          setGroupUnreadCounts(prevCounts => ({
            ...prevCounts,
            [data.group_id]: (prevCounts[data.group_id] || 0) + 1
          }));
        }
        
        // Show browser notification for group messages
        if (data.sender_id !== currentUser?.id && document.hidden && Notification.permission === 'granted') {
          // Get sender username
          const sender = users.find(u => u.id === data.sender_id);
          const senderName = sender ? sender.username : 'Someone';
          const group = groups.find(g => g.id === data.group_id);
          const groupName = group ? group.name : 'Group';
          
          new Notification(`${senderName} in ${groupName}`, {
            body: data.has_media ? (data.media_type === 'image' ? '📷 Photo' : '🎥 Video') : data.content,
            icon: '/favicon.ico'
          });
        }
      } else if (data.type === 'notification') {
        // Handle real-time notification
        console.log('Received notification:', data);
        
        // Only process notification if current user is the receiver
        // For individual messages, check receiver_id
        // For group messages, check if it's a group notification
        const isRecipient = data.receiver_id === currentUser?.id || data.is_group;
        
        if (isRecipient && data.sender_id !== currentUser?.id) {
          // Update user list to move sender to top (only for individual messages)
          if (data.receiver_id === currentUser?.id) {
            setUsers(prevUsers => {
              // Move sender to top of list
              const updatedUsers = [...prevUsers];
              const senderIndex = updatedUsers.findIndex(u => u.id === data.sender_id);
              if (senderIndex !== -1) {
                const [sender] = updatedUsers.splice(senderIndex, 1);
                updatedUsers.unshift(sender);
              }
              return updatedUsers;
            });
            
            // Update unread count for notifications only if not viewing this conversation
            if (!selectedUser || selectedUser.id !== data.sender_id) {
              setUnreadCounts(prevCounts => ({
                ...prevCounts,
                [data.sender_id]: (prevCounts[data.sender_id] || 0) + 1
              }));
            }
          }
          
          // Show browser notification if supported and window is not focused
          if (document.hidden && Notification.permission === 'granted') {
            const notificationTitle = data.is_group 
              ? `${data.sender_username} in ${data.group_name}`
              : data.sender_username || 'New Message';
            
            new Notification(notificationTitle, {
              body: `${data.has_media ? (data.media_type === 'image' ? '📷 Photo' : '🎥 Video') : data.content}`,
              icon: '/favicon.ico'
            });
          }
        }
      } else if (data.type === 'read_status') {
        // Handle real-time read status updates
        console.log('Received read status update:', data);
        
        // Update message read status in state for current conversation
        console.log('Updating message read status for message:', data.message_id);
        
        setMessages(prevMessages => {
          const updatedMessages = prevMessages.map(msg => 
            msg.id === data.message_id ? {...msg, is_read: true} : msg
          );
          console.log('Updated messages:', updatedMessages);
          return updatedMessages;
        });
      } else if (data.type === 'group_read_status') {
        // Handle group read status updates
        console.log('Received group read status update:', data);
        
        // Update group messages read status
        setGroupMessages(prevMessages => {
          return prevMessages.map(msg => {
            if (msg.group_id === data.group_id && msg.sender_id === currentUser?.id) {
              // Mark messages as read by this reader
              return {...msg, is_read: true};
            }
            return msg;
          });
        });
      } else if (data.type === 'error') {
        if (data.message === 'Token has expired') {
          alert('Your session has expired. Please log in again.');
          handleLogout();
        }
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setWebsocket(null);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    // Cleanup function
    return () => {
      if (ws) {
        ws.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  // Fetch messages when selected user changes
  useEffect(() => {
    if (selectedUser && currentUser) {
      const fetchMessages = async () => {
        try {
          const response = await fetch(`${CONFIG.API_BASE_URL}/api/messages/${selectedUser.id}`, {
            headers: {
              'Authorization': `Bearer ${authToken}`
            }
          });
          
          if (response.status === 401) {
            // Token expired or invalid
            handleLogout();
            return;
          }
          
          const data = await response.json();
          // Filter messages for the selected conversation
          const conversationMessages = data.filter(msg => 
            (msg.sender_id === currentUser.id && msg.receiver_id === selectedUser.id) ||
            (msg.sender_id === selectedUser.id && msg.receiver_id === currentUser.id)
          );
          setMessages(conversationMessages);
          
          // Mark unread messages as read
          const unreadMessageIds = conversationMessages
            .filter(msg => msg.sender_id === selectedUser.id && !msg.is_read)
            .map(msg => msg.id);
            
          if (unreadMessageIds.length > 0) {
            // Send read status via WebSocket if available
            if (websocket && websocket.readyState === WebSocket.OPEN) {
              console.log('Sending read status via WebSocket');
              const readStatusData = {
                type: 'read_status',
                message_ids: unreadMessageIds
              };
              
              websocket.send(JSON.stringify(readStatusData));
              console.log('Read status sent via WebSocket:', readStatusData);
              
              // Update local state to mark messages as read
              setMessages(prevMessages => 
                prevMessages.map(msg => 
                  unreadMessageIds.includes(msg.id) ? {...msg, is_read: true} : msg
                )
              );
            } else {
              // Fallback to HTTP request
              try {
                await fetch(`${CONFIG.API_BASE_URL}/api/messages/read`, {
                  method: 'PUT',
                  headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                  },
                  body: JSON.stringify({
                    message_ids: unreadMessageIds
                  })
                });
                
                // Update local state to mark messages as read
                setMessages(prevMessages => 
                  prevMessages.map(msg => 
                    unreadMessageIds.includes(msg.id) ? {...msg, is_read: true} : msg
                  )
                );
              } catch (error) {
                console.error('Error marking messages as read:', error);
              }
            }
          }
          
          // Clear unread count for this user
          setUnreadCounts(prevCounts => {
            const newCounts = {...prevCounts};
            delete newCounts[selectedUser.id];
            return newCounts;
          });
        } catch (error) {
          console.error('Error fetching messages:', error);
        }
      };

      fetchMessages();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUser, authToken, currentUser, websocket]);

  // Fetch group messages when selected group changes
  useEffect(() => {
    if (selectedGroup && currentUser) {
      const fetchGroupMessages = async () => {
        try {
          const response = await fetch(`${CONFIG.API_BASE_URL}/api/group-messages/${selectedGroup.id}`, {
            headers: {
              'Authorization': `Bearer ${authToken}`
            }
          });
          
          if (response.status === 401) {
            handleLogout();
            return;
          }
          
          const data = await response.json();
          setGroupMessages(data);
          
          // Send group read status via WebSocket
          if (websocket && websocket.readyState === WebSocket.OPEN) {
            console.log('Sending group read status via WebSocket');
            const readStatusData = {
              type: 'group_read_status',
              group_id: selectedGroup.id
            };
            
            websocket.send(JSON.stringify(readStatusData));
            console.log('Group read status sent via WebSocket:', readStatusData);
          }
          
          // Clear unread count for this group
          setGroupUnreadCounts(prevCounts => {
            const newCounts = {...prevCounts};
            delete newCounts[selectedGroup.id];
            return newCounts;
          });
        } catch (error) {
          console.error('Error fetching group messages:', error);
        }
      };

      fetchGroupMessages();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedGroup, authToken, currentUser, websocket]);

  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, groupMessages]);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleCancelFile = () => {
    setSelectedFile(null);
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    
    // Handle media message if file is selected
    if (selectedFile) {
      await handleSendMediaMessage();
      return;
    }
    
    // Handle text message
    if (!newMessage.trim() || (!selectedUser && !selectedGroup) || !currentUser) return;

    const messageContent = newMessage;
    setNewMessage(''); // Clear input immediately for better UX
    setSelectedFile(null); // Clear selected file

    if (selectedUser) {
      // Individual message
      // If WebSocket is available, use it for real-time messaging
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        console.log('Sending message via WebSocket');
        const messageData = {
          type: 'message',
          receiver_id: selectedUser.id,
          content: messageContent
        };
        
        websocket.send(JSON.stringify(messageData));
        console.log('Message sent via WebSocket:', messageData);
        
        // Don't add optimistic message - wait for websocket confirmation
        // This prevents duplicates
      } else {
        console.log('WebSocket not available, using HTTP fallback');
        // Fallback to HTTP request
        try {
          const response = await fetch(`${CONFIG.API_BASE_URL}/api/messages`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
              receiver_id: selectedUser.id,
              content: messageContent
            })
          });

          if (response.status === 401) {
            // Token expired or invalid
            handleLogout();
            return;
          }

          const data = await response.json();
          if (response.ok) {
            console.log('Message sent via HTTP:', data);
            setMessages(prevMessages => [...prevMessages, data]);
          }
        } catch (error) {
          console.error('Error sending message:', error);
        }
      }
      
      // Clear unread count for this user after sending a message
      setUnreadCounts(prevCounts => {
        const newCounts = {...prevCounts};
        delete newCounts[selectedUser.id];
        return newCounts;
      });
    } else if (selectedGroup) {
      // Group message
      // If WebSocket is available, use it for real-time messaging
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        console.log('Sending group message via WebSocket');
        const messageData = {
          type: 'group_message',
          group_id: selectedGroup.id,
          content: messageContent
        };
        
        websocket.send(JSON.stringify(messageData));
        console.log('Group message sent via WebSocket:', messageData);
        
        // Don't add optimistic message - wait for websocket confirmation
        // This prevents duplicates
      } else {
        console.log('WebSocket not available, using HTTP fallback for group message');
        // Fallback to HTTP request for group messages
        try {
          const response = await fetch(`${CONFIG.API_BASE_URL}/api/group-messages`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
              group_id: selectedGroup.id,
              content: messageContent
            })
          });

          if (response.status === 401) {
            // Token expired or invalid
            handleLogout();
            return;
          }

          const data = await response.json();
          if (response.ok) {
            console.log('Group message sent via HTTP:', data);
            // For now, we're not adding group messages to the local state
            // In a full implementation, we would fetch group messages separately
          }
        } catch (error) {
          console.error('Error sending group message:', error);
        }
      }
    }
  };

  const handleSendMediaMessage = async () => {
    if (!selectedFile || !selectedUser || !currentUser) return;

    try {
      // Upload file to Cloudinary
      const formData = new FormData();
      formData.append('file', selectedFile);
      
      const uploadResponse = await fetch(`${CONFIG.API_BASE_URL}/api/upload-media`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        body: formData
      });

      if (uploadResponse.status === 401) {
        // Token expired or invalid
        handleLogout();
        return;
      }

      const uploadData = await uploadResponse.json();
      
      if (!uploadResponse.ok) {
        console.error('Upload failed:', uploadData);
        alert('Failed to upload media. Please try again.');
        return;
      }

      // Send media message via WebSocket if available
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        console.log('Sending media message via WebSocket');
        const messageData = {
          type: 'message',
          receiver_id: selectedUser.id,
          content: '',
          media_url: uploadData.url,
          media_type: uploadData.type
        };
        
        websocket.send(JSON.stringify(messageData));
        console.log('Media message sent via WebSocket:', messageData);
      } else {
        // Fallback to HTTP request
        console.log('WebSocket not available, using HTTP fallback for media message');
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/send-media-message`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify({
            receiver_id: selectedUser.id,
            media_url: uploadData.url,
            media_type: uploadData.type
          })
        });

        if (response.status === 401) {
          // Token expired or invalid
          handleLogout();
          return;
        }

        const data = await response.json();
        if (response.ok) {
          console.log('Media message sent via HTTP:', data);
          setMessages(prevMessages => [...prevMessages, data]);
        }
      }
      
      // Clear selected file
      setSelectedFile(null);
    } catch (error) {
      console.error('Error sending media message:', error);
      alert('Failed to send media message. Please try again.');
    }
  };

  const handleLogout = () => {
    console.log('Logging out...');
    localStorage.removeItem('token');
    if (onLogout) onLogout();
    navigate('/login');
  };
  
  // Function to clear notifications for a user
  const clearUserNotifications = (userId) => {
    setUnreadCounts(prevCounts => {
      const newCounts = {...prevCounts};
      delete newCounts[userId];
      return newCounts;
    });
  };
  
  // Function to select user and clear their notifications
  const handleSelectUser = (user) => {
    setSelectedUser(user);
    setSelectedGroup(null);
    clearUserNotifications(user.id);
  };
  
  // Function to select group
  const handleSelectGroup = (group) => {
    setSelectedGroup(group);
    setSelectedUser(null);
    // Clear notifications for this group
    setGroupUnreadCounts(prevCounts => {
      const newCounts = {...prevCounts};
      delete newCounts[group.id];
      return newCounts;
    });
  };
  


  const handleShowSecurityCodes = async () => {
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/api/security-codes/${currentUser?.email}`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      if (response.status === 401) {
        handleLogout();
        return;
      }
      
      const data = await response.json();
      
      // Display security codes in an alert (in a real app, you'd show them in a modal)
      alert(`Your security codes:\n${data.security_codes.join('\n')}`);
    } catch (error) {
      console.error('Error fetching security codes:', error);
      alert('Error fetching security codes. Please try again.');
    }
  };
  
  const handleCreateGroup = async (e) => {
    e.preventDefault();
    
    console.log('Creating group with name:', groupName);
    console.log('Group members:', groupMembers);
    console.log('Auth token:', authToken ? `${authToken.substring(0, 10)}...` : 'None');
    
    if (!groupName.trim()) {
      alert('Please enter a group name');
      return;
    }
    
    if (groupMembers.length === 0) {
      alert('Please select at least one member');
      return;
    }
    
    try {
      console.log('Sending request to create group...');
      console.log('Request URL: http://localhost:8000/api/groups');
      console.log('Request method: POST');
      console.log('Request headers:', {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken ? authToken.substring(0, 10) + '...' : 'None'}`
      });
      console.log('Request body:', JSON.stringify({
        name: groupName,
        members: groupMembers
      }));
      
      // First test if we can reach the endpoint at all
      console.log('Testing if endpoint exists...');
      try {
        const optionsResponse = await fetch('http://localhost:8000/api/groups', { method: 'OPTIONS' });
        console.log('OPTIONS response status:', optionsResponse.status);
        console.log('OPTIONS response headers:', optionsResponse.headers);
      } catch (optionsError) {
        console.error('OPTIONS request failed:', optionsError);
      }
      
      // Test debug endpoint
      console.log('Testing debug endpoint...');
      try {
        const debugResponse = await fetch('http://localhost:8000/api/debug-create-group', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify({
            name: groupName,
            members: groupMembers
          })
        });
        console.log('Debug endpoint response status:', debugResponse.status);
        if (debugResponse.ok) {
          const debugData = await debugResponse.json();
          console.log('Debug endpoint response:', debugData);
        }
      } catch (debugError) {
        console.error('Debug endpoint failed:', debugError);
      }
      
      const response = await fetch(`${CONFIG.API_BASE_URL}/api/groups`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          name: groupName,
          members: groupMembers
        })
      });
      
      console.log('Group creation response status:', response.status);
      console.log('Group creation response headers:', response.headers);
      console.log('Group creation response ok:', response.ok);
      
      if (response.status === 401) {
        console.log('Unauthorized - logging out');
        handleLogout();
        return;
      }
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Group creation failed with response:', errorText);
        throw new Error(`Failed to create group: ${response.status} ${response.statusText}`);
      }
      
      const newGroup = await response.json();
      console.log('Group created successfully:', newGroup);
      
      // Add the new group to the groups list
      setGroups(prevGroups => [...prevGroups, newGroup]);
      
      // Reset form
      setGroupName('');
      setGroupMembers([]);
      setShowCreateGroup(false);
      
      alert('Group created successfully!');
    } catch (error) {
      console.error('Error creating group:', error);
      if (error instanceof TypeError && error.message.includes('fetch')) {
        console.error('Network error - server may be unreachable');
        alert('Network error - unable to connect to server. Please make sure the server is running.');
      } else {
        alert(`Error creating group: ${error.message}`);
      }
    }
  };
  
  const toggleGroupMember = (userId) => {
    setGroupMembers(prevMembers => 
      prevMembers.includes(userId) 
        ? prevMembers.filter(id => id !== userId)
        : [...prevMembers, userId]
    );
  };
  

  
  const handleAcceptInvitation = async (invitationId) => {
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/api/group-invitations/${invitationId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          status: 'accepted'
        })
      });
      
      if (response.status === 401) {
        handleLogout();
        return;
      }
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to accept invitation');
      }
      
      await response.json();
      
      // Refresh groups list to include the newly joined group
      const groupsResponse = await fetch(`${CONFIG.API_BASE_URL}/api/groups`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      if (groupsResponse.ok) {
        const groupsData = await groupsResponse.json();
        setGroups(groupsData);
      }
      
      alert('Invitation accepted! You are now a member of the group.');
    } catch (error) {
      console.error('Error accepting invitation:', error);
      alert(`Error accepting invitation: ${error.message}`);
    }
  };
  
  const handleRejectInvitation = async (invitationId) => {
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/api/group-invitations/${invitationId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          status: 'rejected'
        })
      });
      
      if (response.status === 401) {
        handleLogout();
        return;
      }
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to reject invitation');
      }
      
      await response.json();
      alert('Invitation rejected.');
    } catch (error) {
      console.error('Error rejecting invitation:', error);
      alert(`Error rejecting invitation: ${error.message}`);
    }
  };

  const handleOpenGroupSettings = (group) => {
    setEditingGroup(group);
    setGroupName(group.name);
    setGroupProfilePreview(group.profile_picture || '');
    setGroupProfilePicture(null);
    setShowGroupSettings(true);
  };

  const handleGroupPictureChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setGroupProfilePicture(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setGroupProfilePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleUpdateGroup = async (e) => {
    e.preventDefault();
    
    if (!editingGroup) return;
    
    try {
      let profilePictureUrl = editingGroup.profile_picture;
      
      // Upload new profile picture if selected
      if (groupProfilePicture) {
        const formData = new FormData();
        formData.append('file', groupProfilePicture);
        
        const uploadResponse = await fetch(`${CONFIG.API_BASE_URL}/api/upload-group-picture`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authToken}`
          },
          body: formData
        });
        
        if (uploadResponse.status === 401) {
          handleLogout();
          return;
        }
        
        if (!uploadResponse.ok) {
          throw new Error('Failed to upload group picture');
        }
        
        const uploadData = await uploadResponse.json();
        profilePictureUrl = uploadData.url;
      }
      
      // Update group
      const response = await fetch(`${CONFIG.API_BASE_URL}/api/groups/${editingGroup.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          name: groupName !== editingGroup.name ? groupName : undefined,
          profile_picture: profilePictureUrl !== editingGroup.profile_picture ? profilePictureUrl : undefined
        })
      });
      
      if (response.status === 401) {
        handleLogout();
        return;
      }
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update group');
      }
      
      const updatedGroup = await response.json();
      
      // Update groups list
      setGroups(prevGroups => 
        prevGroups.map(g => g.id === updatedGroup.id ? updatedGroup : g)
      );
      
      // Update selected group if it's the one being edited
      if (selectedGroup && selectedGroup.id === updatedGroup.id) {
        setSelectedGroup(updatedGroup);
      }
      
      setShowGroupSettings(false);
      setEditingGroup(null);
      alert('Group updated successfully!');
    } catch (error) {
      console.error('Error updating group:', error);
      alert(`Error updating group: ${error.message}`);
    }
  };

  return (
    <div className="chat-container">
      {/* Left Sidebar - Users List */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>Get Chat</h2>
          <div className="header-actions">
            <div className="create-group-icon" onClick={() => setShowCreateGroup(true)}>
              +
            </div>
            <div className="settings-icon" onClick={() => setShowSettings(!showSettings)}>
              ⚙️
            </div>
          </div>
          {showSettings && (
            <div className="settings-dropdown">
              <button onClick={handleShowSecurityCodes}>Security Codes</button>
              <button onClick={() => setShowInvitations(true)}>Group Invitations ({invitations.length})</button>
              <button onClick={onShowProfile}>Profile</button>
              <button onClick={handleLogout}>Logout</button>
            </div>
          )}
          {showInvitations && (
            <div className="modal-overlay" onClick={() => setShowInvitations(false)}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>Group Invitations</h3>
                  <button className="modal-close" onClick={() => setShowInvitations(false)}>×</button>
                </div>
                <div className="invitations-list">
                  {invitations.length === 0 ? (
                    <p className="no-invitations">No pending invitations</p>
                  ) : (
                    invitations.map(invitation => (
                      <div key={invitation.id} className="invitation-item">
                        <div className="invitation-info">
                          <h4>{invitation.group_name}</h4>
                          <p>Invited by user ID: {invitation.invited_by}</p>
                          <p className="invitation-date">
                            {new Date(invitation.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="invitation-actions">
                          <button 
                            className="btn-secondary"
                            onClick={() => handleRejectInvitation(invitation.id)}
                          >
                            Reject
                          </button>
                          <button 
                            className="btn-primary"
                            onClick={() => handleAcceptInvitation(invitation.id)}
                          >
                            Accept
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
          {showGroupSettings && (
            <div className="modal-overlay" onClick={() => setShowGroupSettings(false)}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>Group Settings</h3>
                  <button className="modal-close" onClick={() => setShowGroupSettings(false)}>×</button>
                </div>
                <form onSubmit={handleUpdateGroup}>
                  <div className="form-group">
                    <label>Group Picture</label>
                    <div className="profile-picture-section">
                      <div className="profile-picture-preview">
                        {groupProfilePreview ? (
                          <img src={groupProfilePreview} alt="Group" className="profile-image" />
                        ) : (
                          <div className="profile-placeholder">
                            {groupName ? groupName.charAt(0).toUpperCase() : 'G'}
                          </div>
                        )}
                      </div>
                      <div className="profile-picture-upload">
                        <label htmlFor="group-picture" className="upload-button">
                          Change Group Picture
                        </label>
                        <input
                          type="file"
                          id="group-picture"
                          accept="image/*"
                          onChange={handleGroupPictureChange}
                          style={{ display: 'none' }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="form-group">
                    <label htmlFor="groupName">Group Name</label>
                    <input
                      type="text"
                      id="groupName"
                      value={groupName}
                      onChange={(e) => setGroupName(e.target.value)}
                      placeholder="Enter group name"
                      className="form-control"
                    />
                  </div>
                  <div className="form-actions">
                    <button type="button" className="btn-secondary" onClick={() => setShowGroupSettings(false)}>
                      Cancel
                    </button>
                    <button type="submit" className="btn-primary">
                      Save Changes
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
          {showCreateGroup && (
            <div className="modal-overlay" onClick={() => setShowCreateGroup(false)}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>Create New Group</h3>
                  <button className="modal-close" onClick={() => setShowCreateGroup(false)}>×</button>
                </div>
                <form onSubmit={handleCreateGroup}>
                  <div className="form-group">
                    <label htmlFor="groupName">Group Name</label>
                    <input
                      type="text"
                      id="groupName"
                      value={groupName}
                      onChange={(e) => setGroupName(e.target.value)}
                      placeholder="Enter group name"
                      className="form-control"
                    />
                  </div>
                  <div className="form-group">
                    <label>Select Members</label>
                    <div className="members-list">
                      {users.filter(user => user.id !== currentUser?.id).map(user => (
                        <div 
                          key={user.id} 
                          className={`member-item ${groupMembers.includes(user.id) ? 'selected' : ''}`}
                          onClick={() => toggleGroupMember(user.id)}
                        >
                          <div className="member-avatar">
                            {user.profile_picture ? (
                              <img src={user.profile_picture} alt={user.username} />
                            ) : (
                              user.username.charAt(0).toUpperCase()
                            )}
                          </div>
                          <div className="member-name">{user.username}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="form-actions">
                    <button type="button" className="btn-secondary" onClick={() => setShowCreateGroup(false)}>
                      Cancel
                    </button>
                    <button type="submit" className="btn-primary">
                      Create Group
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
        <div className="search-container">
          <input
            type="text"
            placeholder="Search users..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="users-list">
          {(() => {
            // Combine users and groups into a single list
            const combinedList = [
              ...filteredUsers.map(user => ({ ...user, type: 'user' })),
              ...(Array.isArray(groups) ? groups.map(group => ({ ...group, type: 'group' })) : [])
            ];
            
            // Sort by most recent activity (simplified for now)
            const sortedList = [...combinedList].sort((a, b) => {
              // This is a simplified sort - in a real app you'd sort by last message timestamp
              return a.type === 'group' ? -1 : 1;
            });
            
            return sortedList.map(item => {
              if (item.type === 'user') {
                // Get the last message for this user
                const lastMessage = messages
                  .filter(msg => 
                    (msg.sender_id === currentUser?.id && msg.receiver_id === item.id) ||
                    (msg.sender_id === item.id && msg.receiver_id === currentUser?.id)
                  )
                  .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0];
                
                return (
                  <div
                    key={item.id}
                    className={`user-item ${selectedUser && selectedUser.id === item.id ? 'selected' : ''}`}
                    onClick={() => handleSelectUser(item)}
                  >
                    <div className="user-avatar">
                      {item.profile_picture ? (
                        <img src={item.profile_picture} alt={item.username} className="user-avatar-img" />
                      ) : (
                        item.username.charAt(0).toUpperCase()
                      )}
    {(unreadCounts[item.id] || 0) > 0 && (
                        <div className="unread-indicator" />
                      )}
                    </div>
                    <div className="user-info">
                      <div className="user-name">
                        {item.username}
                        <span className="last-message-time">
                          {lastMessage && new Date(lastMessage.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div className="last-message-preview">
                        {lastMessage ? (
                          lastMessage.media_url ? 
                            (lastMessage.media_type === 'image' ? '📷 Photo' : '🎥 Video') :
                            (lastMessage.sender_id === currentUser?.id ? `You: ${lastMessage.content}` : lastMessage.content)
                        ) : (
                          'No messages yet'
                        )}
                        {(unreadCounts[item.id] || 0) > 0 && (
                          <span className="unread-count">{unreadCounts[item.id]}</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              } else {
                // Group item
                const lastGroupMessage = groupMessages
                  .filter(msg => msg.group_id === item.id)
                  .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0];
                
                return (
                  <div
                    key={item.id}
                    className={`group-item ${selectedGroup && selectedGroup.id === item.id ? 'selected' : ''}`}
                    onClick={() => handleSelectGroup(item)}
                  >
                    <div className="group-avatar">
                      {item.profile_picture ? (
                        <img src={item.profile_picture} alt={item.name} className="group-avatar-img" />
                      ) : (
                        item.name.charAt(0).toUpperCase()
                      )}
                      {(groupUnreadCounts[item.id] || 0) > 0 && (
                        <div className="unread-indicator" />
                      )}
                    </div>
                    <div className="group-info">
                      <div className="group-name">
                        {item.name}
                        <span className="group-last-message-time">
                          {lastGroupMessage && new Date(lastGroupMessage.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div className="group-members">
                        {item.members.length} members
                        {(groupUnreadCounts[item.id] || 0) > 0 && (
                          <span className="unread-count">{groupUnreadCounts[item.id]}</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              }
            });
          })()}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-area">
        {selectedUser || selectedGroup ? (
          <>
            <div className="chat-header">
              {selectedUser ? (
                <div className="chat-user-info">
                  <div className="chat-user-avatar">
                    {selectedUser.profile_picture ? (
                      <img src={selectedUser.profile_picture} alt={selectedUser.username} className="chat-user-avatar-img" />
                    ) : (
                      selectedUser.username.charAt(0).toUpperCase()
                    )}
                  </div>
                  <div className="chat-user-name">{selectedUser.username}</div>
                </div>
              ) : selectedGroup ? (
                <div className="chat-group-info">
                  <div className="chat-group-avatar">
                    {selectedGroup.profile_picture ? (
                      <img src={selectedGroup.profile_picture} alt={selectedGroup.name} className="chat-group-avatar-img" />
                    ) : (
                      selectedGroup.name.charAt(0).toUpperCase()
                    )}
                  </div>
                  <div className="chat-group-details">
                    <div className="chat-group-name">{selectedGroup.name}</div>
                    <div className="chat-group-members">{selectedGroup.members.length} members</div>
                  </div>
                  {selectedGroup.members.some(m => m.user_id === currentUser?.id && m.role === 'admin') && (
                    <button 
                      className="group-settings-button"
                      onClick={() => handleOpenGroupSettings(selectedGroup)}
                      title="Group Settings"
                    >
                      ⚙️
                    </button>
                  )}
                </div>
              ) : null}
            </div>
            <div className="messages-container">
              {(() => {
                let filteredMessages = [];
                if (selectedUser) {
                  // Filter messages for individual chat
                  filteredMessages = messages.filter(msg => 
                    (msg.sender_id === currentUser?.id && msg.receiver_id === selectedUser.id) ||
                    (msg.sender_id === selectedUser.id && msg.receiver_id === currentUser?.id)
                  );
                } else if (selectedGroup) {
                  // Filter messages for group chat
                  filteredMessages = groupMessages.filter(msg => msg.group_id === selectedGroup.id);
                }
                
                console.log('All messages:', messages);
                console.log('All group messages:', groupMessages);
                console.log('Current user ID:', currentUser?.id);
                console.log('Selected user ID:', selectedUser?.id);
                console.log('Selected group ID:', selectedGroup?.id);
                console.log('Filtered messages:', filteredMessages);
                return filteredMessages;
              })().map(message => {
                // Get sender info for group messages
                const sender = selectedGroup ? users.find(u => u.id === message.sender_id) : null;
                
                return (
                  <div
                    key={message.id}
                    className={`message ${message.sender_id === currentUser?.id ? 'sent' : 'received'}`}
                  >
                    {selectedGroup && message.sender_id !== currentUser?.id && (
                      <div className="message-sender-name">
                        {sender ? sender.username : 'Unknown'}
                      </div>
                    )}
                    <div className="message-content">
                      {message.media_url ? (
                        message.media_type === 'image' ? (
                          <img 
                            src={message.media_url} 
                            alt="Shared content" 
                            className="media-content"
                            style={{ maxWidth: '300px', maxHeight: '300px', borderRadius: '8px' }}
                          />
                        ) : (
                          <video 
                            src={message.media_url} 
                            controls 
                            className="media-content"
                            style={{ maxWidth: '300px', maxHeight: '300px', borderRadius: '8px' }}
                          />
                        )
                      ) : (
                        message.content
                      )}
                    </div>
                    <div className="message-time">
                      {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                    {message.sender_id === currentUser?.id && (
                      <div className="message-status">
                        {message.is_read ? (
                          <span className="seen-status">✓✓</span>
                        ) : (
                          <span className="sent-status">✓</span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
            <div className="message-input-container">
              {selectedUser || selectedGroup ? (
                <form onSubmit={handleSendMessage}>
                  <div className="message-input-wrapper">
                    <input
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      placeholder={selectedGroup ? `Message ${selectedGroup.name}...` : "Type a message..."}
                    />
                    <label className="file-upload-label">
                      <input
                        type="file"
                        accept="image/*,video/*"
                        onChange={handleFileSelect}
                        style={{ display: 'none' }}
                      />
                      📎
                    </label>
                    {selectedFile && (
                      <div className="file-preview">
                        <span className="file-name">{selectedFile.name}</span>
                        <button 
                          type="button" 
                          className="cancel-file-button"
                          onClick={handleCancelFile}
                        >
                          ✕
                        </button>
                      </div>
                    )}
                    <button type="submit">Send</button>
                  </div>
                </form>
              ) : (
                <div className="no-chat-selected">
                  <h3>Select a user or group to start chatting</h3>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="no-chat-selected">
            <h3>Select a user or group to start chatting</h3>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatPage;