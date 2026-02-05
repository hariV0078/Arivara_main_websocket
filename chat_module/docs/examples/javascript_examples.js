/**
 * Chatbot Plugin API - JavaScript/TypeScript Examples
 */

const API_BASE_URL = 'https://api.example.com/api';
const JWT_TOKEN = 'YOUR_JWT_TOKEN_HERE';

/**
 * Chatbot API Client
 */
class ChatbotClient {
  constructor(apiUrl, jwtToken) {
    this.apiUrl = apiUrl;
    this.jwtToken = jwtToken;
  }

  /**
   * Get default headers
   */
  getHeaders(contentType = 'application/json') {
    const headers = {
      'Authorization': `Bearer ${this.jwtToken}`
    };
    if (contentType) {
      headers['Content-Type'] = contentType;
    }
    return headers;
  }

  /**
   * Health check
   */
  async healthCheck() {
    const response = await fetch(`${this.apiUrl}/health`);
    return await response.json();
  }

  /**
   * Send a message to the chatbot
   */
  async sendMessage(message, options = {}) {
    const {
      chatId = null,
      images = null,
      enableWebScraping = true
    } = options;

    const payload = {
      message,
      enable_web_scraping: enableWebScraping
    };

    if (chatId) {
      payload.chat_id = chatId;
    }

    if (images) {
      payload.images = images;
    }

    const response = await fetch(`${this.apiUrl}/chat`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get all chats
   */
  async getChats(page = 1, pageSize = 20) {
    const response = await fetch(
      `${this.apiUrl}/chat/chats?page=${page}&page_size=${pageSize}`,
      {
        headers: this.getHeaders()
      }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get a specific chat with messages
   */
  async getChat(chatId) {
    const response = await fetch(
      `${this.apiUrl}/chat/chats/${chatId}`,
      {
        headers: this.getHeaders()
      }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Create a new chat
   */
  async createChat(heading = null) {
    const payload = {};
    if (heading) {
      payload.heading = heading;
    }

    const response = await fetch(`${this.apiUrl}/chat/chats`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Update chat heading
   */
  async updateChatHeading(chatId, heading) {
    const response = await fetch(
      `${this.apiUrl}/chat/chats/${chatId}/heading`,
      {
        method: 'PUT',
        headers: this.getHeaders(),
        body: JSON.stringify({ heading })
      }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Delete a chat
   */
  async deleteChat(chatId) {
    const response = await fetch(
      `${this.apiUrl}/chat/chats/${chatId}`,
      {
        method: 'DELETE',
        headers: this.getHeaders()
      }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Upload an image file
   */
  async uploadImage(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.apiUrl}/chat/upload-image`, {
      method: 'POST',
      headers: this.getHeaders(null), // Don't set Content-Type for FormData
      body: formData
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Convert file to base64
   */
  async fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = error => reject(error);
    });
  }

  /**
   * Send message with image
   */
  async sendMessageWithImage(message, imageFile, chatId = null) {
    const base64Image = await this.fileToBase64(imageFile);
    return await this.sendMessage(message, {
      chatId,
      images: [base64Image],
      enableWebScraping: false
    });
  }
}

// Example usage
async function examples() {
  const client = new ChatbotClient(API_BASE_URL, JWT_TOKEN);

  try {
    // Health check
    console.log('Health Check:');
    const health = await client.healthCheck();
    console.log(health);
    console.log();

    // Send a message
    console.log('Sending message...');
    const response = await client.sendMessage(
      "What's the weather today?",
      { enableWebScraping: true }
    );
    console.log('Response:', response.data.message);
    console.log('Chat ID:', response.data.chat_id);
    if (response.metadata?.sources) {
      console.log('Sources:', response.metadata.sources);
    }
    console.log();

    // Get all chats
    console.log('Getting chats...');
    const chats = await client.getChats();
    console.log(`Total chats: ${chats.total}`);
    chats.data.forEach(chat => {
      console.log(`  - ${chat.heading} (${chat.id})`);
    });
    console.log();

    // Get specific chat
    if (chats.data.length > 0) {
      const chatId = chats.data[0].id;
      console.log(`Getting chat ${chatId}...`);
      const chat = await client.getChat(chatId);
      console.log(`Messages: ${chat.data.messages.length}`);
      chat.data.messages.forEach(msg => {
        console.log(`  [${msg.role}]: ${msg.content.substring(0, 50)}...`);
      });
      console.log();
    }

    // Upload image example
    // const fileInput = document.querySelector('input[type="file"]');
    // if (fileInput.files.length > 0) {
    //   const file = fileInput.files[0];
    //   console.log('Uploading image...');
    //   const uploadResult = await client.uploadImage(file);
    //   console.log('Image URL:', uploadResult.data.url);
    //   console.log();
    // }

    // Send message with image example
    // const fileInput = document.querySelector('input[type="file"]');
    // if (fileInput.files.length > 0) {
    //   const file = fileInput.files[0];
    //   console.log('Sending message with image...');
    //   const response = await client.sendMessageWithImage(
    //     "What's in this image?",
    //     file
    //   );
    //   console.log('Response:', response.data.message);
    // }

  } catch (error) {
    console.error('Error:', error.message);
  }
}

// React Hook Example
function useChatbot(apiUrl, jwtToken) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const client = React.useMemo(
    () => new ChatbotClient(apiUrl, jwtToken),
    [apiUrl, jwtToken]
  );

  const sendMessage = React.useCallback(async (message, options) => {
    setLoading(true);
    setError(null);
    try {
      const result = await client.sendMessage(message, options);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [client]);

  return { sendMessage, loading, error, client };
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ChatbotClient, useChatbot };
}
