/**
 * API service for verifying GST documents against backend endpoints.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

/**
 * Verifies an uploaded GST PDF document.
 * 
 * @param {File | Blob} file - The GST PDF file to verify.
 * @returns {Promise<Object>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function verifyGSTDocument(file) {
  if (!file) {
    throw new Error('A valid GST PDF document file is required.');
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE_URL}/api/verify/gst`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message || errorBody.error)) {
          errorMessage = errorBody.detail || errorBody.message || errorBody.error;
        }
      } catch {
        // Fallback to response status text if response is not JSON
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches the verification history of processed GST documents.
 * 
 * @returns {Promise<Array>} The parsed JSON array of historical records.
 * @throws {Error} Clear error message if the network request or server fails.
 */
export async function fetchVerificationHistory() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/history/gst`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message || errorBody.error)) {
          errorMessage = errorBody.detail || errorBody.message || errorBody.error;
        }
      } catch {
        // Fallback to response status text if response is not JSON
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching verification history:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

export default {
  verifyGSTDocument,
  fetchVerificationHistory,
};
