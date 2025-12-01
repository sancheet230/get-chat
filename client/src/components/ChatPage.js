import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import './ChatPage.css';

const ChatPage = ({ authToken, currentUser, onLogout, onShowProfile }) => {
  const [users, setUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [websocket, setWebsocket] = useState(null);
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

  // Fetch users when authToken becomes available
  useEffect(() => {
    const fetchUsers = async () => {
      if (!authToken) {
        return;
      }
      
      try {
        const response = await fetch('http://localhost:8000/api/users', {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        
        if (response.status === 401) {
          handleLogout();
          return;
        }
        
        const data = await response.json();
        setUsers(data);
      } catch (error) {
        console.error('Error fetching users:', error);
      }
    };
    
    fetchUsers();
  }, [authToken]);

  // Setup WebSocket connection
  useEffect(() => {
    if (!authToken) return;
    
    const ws = new WebSocket('ws://localhost:8001');
    
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
          timestamp: new Date(data.timestamp)
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
  }, [authToken]);

  // Fetch messages when selected user changes
  useEffect(() => {
    if (selectedUser && currentUser) {
      const fetchMessages = async () => {
        try {
          const response = await fetch(`http://localhost:8000/api/messages/${selectedUser.id}`, {
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
        } catch (error) {
          console.error('Error fetching messages:', error);
        }
      };

      fetchMessages();
    }
  }, [selectedUser, authToken, currentUser]);

  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedUser || !currentUser) return;

    const messageContent = newMessage;
    setNewMessage(''); // Clear input immediately for better UX

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
        const response = await fetch('http://localhost:8000/api/messages', {
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
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    if (onLogout) onLogout();
    navigate('/login');
  };

  const handleShowSecurityCodes = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/security-codes/${currentUser?.email}`, {
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

  return (
    <div className="chat-container">
      {/* Left Sidebar - Users List */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>Get Chat</h2>
          <div className="settings-icon" onClick={() => setShowSettings(!showSettings)}>
            ⚙️
          </div>
          {showSettings && (
            <div className="settings-dropdown">
              <button onClick={handleShowSecurityCodes}>Security Codes</button>
              <button onClick={onShowProfile}>Profile</button>
              <button onClick={handleLogout}>Logout</button>
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
          {filteredUsers.map(user => (
            <div
              key={user.id}
              className={`user-item ${selectedUser && selectedUser.id === user.id ? 'selected' : ''}`}
              onClick={() => setSelectedUser(user)}
            >
              <div className="user-avatar">
                {user.profile_picture ? (
                  <img src={user.profile_picture} alt={user.username} className="user-avatar-img" />
                ) : (
                  user.username.charAt(0).toUpperCase()
                )}
              </div>
              <div className="user-info">
                <div className="user-name">{user.username}</div>
                <div className="user-email">{user.email}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-area">
        {selectedUser ? (
          <>
            <div className="chat-header">
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
            </div>
            <div className="messages-container">
              {(() => {
                const filteredMessages = messages.filter(msg => 
                  (msg.sender_id === currentUser?.id && msg.receiver_id === selectedUser.id) ||
                  (msg.sender_id === selectedUser.id && msg.receiver_id === currentUser?.id)
                );
                console.log('All messages:', messages);
                console.log('Current user ID:', currentUser?.id);
                console.log('Selected user ID:', selectedUser.id);
                console.log('Filtered messages:', filteredMessages);
                return filteredMessages;
              })().map(message => (
                <div
                  key={message.id}
                  className={`message ${message.sender_id === currentUser?.id ? 'sent' : 'received'}`}
                >
                  <div className="message-content">
                    {message.content}
                  </div>
                  <div className="message-time">
                    {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div className="message-input-container">
              <form onSubmit={handleSendMessage}>
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Type a message..."
                />
                <button type="submit">Send</button>
              </form>
            </div>
          </>
        ) : (
          <div className="no-chat-selected">
            <h3>Select a user to start chatting</h3>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatPage;