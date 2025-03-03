// chatbot.js - Place this file in the static folder

document.addEventListener('DOMContentLoaded', function() {
    const chatbotHeader = document.getElementById('chatbot-header');
    const chatbotContent = document.getElementById('chatbot-content');
    const toggleButton = document.getElementById('toggle-chatbot');
    const messagesContainer = document.getElementById('chat-messages');
    const userMessageInput = document.getElementById('user-message');
    const sendButton = document.getElementById('send-message');
    
    // Initialize - start minimized
    chatbotContent.style.display = 'none';
    toggleButton.textContent = 'v';
    
    // Toggle chatbot visibility
    chatbotHeader.addEventListener('click', function() {
        if (chatbotContent.style.display === 'none') {
            chatbotContent.style.display = 'flex';
            toggleButton.textContent = '^';
            // Scroll to bottom of messages
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        } else {
            chatbotContent.style.display = 'none';
            toggleButton.textContent = 'v';
        }
    });
    
    // Send message function
    function sendMessage() {
        const userMessage = userMessageInput.value.trim();
        if (userMessage === '') return;
        
        // Add user message to chat
        addMessage(userMessage, 'user');
        userMessageInput.value = '';
        
        // Send to server
        fetch('/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: userMessage }),
        })
        .then(response => response.json())
        .then(data => {
            // Add bot response to chat
            addMessage(data.response, 'bot');
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        });
    }
    
    // Add a message to the chat
    function addMessage(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
        messageElement.textContent = message;
        messagesContainer.appendChild(messageElement);
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);
    
    // Send message on Enter key
    userMessageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    // Add some suggestions for the user to click
    function addSuggestions() {
        const suggestions = [
            "What is autism?",
            "Autism symptoms",
            "How is autism diagnosed?",
            "Autism treatments"
        ];
        
        const suggestionsContainer = document.createElement('div');
        suggestionsContainer.classList.add('suggestions');
        
        suggestions.forEach(suggestion => {
            const suggestionButton = document.createElement('button');
            suggestionButton.classList.add('suggestion-button');
            suggestionButton.textContent = suggestion;
            suggestionButton.addEventListener('click', function() {
                userMessageInput.value = suggestion;
                sendMessage();
            });
            suggestionsContainer.appendChild(suggestionButton);
        });
        
        messagesContainer.appendChild(suggestionsContainer);
    }
    
    // Add suggestions after a short delay
    setTimeout(addSuggestions, 1000);
});