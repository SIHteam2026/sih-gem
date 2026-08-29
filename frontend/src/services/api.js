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

/**
 * Analyzes an uploaded tender document.
 * 
 * @param {File | Blob} file - The tender document file to analyze.
 * @returns {Promise<Object>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function analyzeTender(file) {
  if (!file) {
    throw new Error('A valid tender document file is required.');
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE_URL}/api/tender/analyze`, {
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
    console.error('Error analyzing tender document:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Classifies an uploaded document to determine its type and validity.
 * 
 * @param {File | Blob} file - The document file to classify.
 * @returns {Promise<Object>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function classifyDocument(file) {
  if (!file) {
    throw new Error('A valid document file is required.');
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE_URL}/api/document/classify`, {
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
    console.error('Error classifying document:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches historical tender analysis records.
 * 
 * @returns {Promise<Array | Object>} The parsed JSON array of tender history records.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function fetchTenderHistory() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/history/tender`, {
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
    console.error('Error fetching tender history:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Compares two entity / company names for similarity and matching.
 * 
 * @param {string} name1 - First entity name.
 * @param {string} name2 - Second entity name.
 * @returns {Promise<Object>} The parsed JSON response comparing the entities.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function compareEntities(name1, name2) {
  try {
    const queryParams = new URLSearchParams({
      name1: String(name1 || ''),
      name2: String(name2 || ''),
    });

    const response = await fetch(`${API_BASE_URL}/api/entity/compare?${queryParams.toString()}`, {
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
    console.error('Error comparing entities:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Batch classifies documents packaged in a zip archive.
 * 
 * @param {File | Blob} zipFile - The zip file containing documents to classify.
 * @returns {Promise<Object>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function batchClassifyDocuments(zipFile) {
  if (!zipFile) {
    throw new Error('A valid ZIP archive file is required for batch classification.');
  }

  const formData = new FormData();
  formData.append('file', zipFile);

  try {
    const response = await fetch(`${API_BASE_URL}/api/document/batch-classify`, {
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
    console.error('Error in batch document classification:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Verifies a bidder evidence document against a tender requirement.
 * 
 * @param {File | Blob} tenderFile - The tender RFP / criteria document.
 * @param {File | Blob} bidderFile - The bidder evidence document.
 * @param {string | number} requirementId - The target requirement ID to evaluate against.
 * @returns {Promise<Object>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function verifyBid(tenderFile, bidderFile, requirementId) {
  if (!tenderFile || !bidderFile || !requirementId) {
    throw new Error('Tender file, bidder file, and requirement ID are all required to verify a bid.');
  }

  const formData = new FormData();
  formData.append('tender_file', tenderFile);
  formData.append('bidder_file', bidderFile);
  formData.append('requirement_id', String(requirementId));

  try {
    const response = await fetch(`${API_BASE_URL}/api/verify/bid`, {
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
    console.error('Error verifying bid evidence:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Asks a natural language procurement question with optional context text.
 *
 * @param {string} question - The procurement question to ask the AI.
 * @param {string} [contextText] - Optional context text (e.g. tender clause, document extract).
 * @returns {Promise<Object>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function askProcurementQuestion(question, contextText = '') {
  if (!question || !String(question).trim()) {
    throw new Error('A non-empty question is required to query the procurement assistant.');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question: String(question).trim(),
        context_text: String(contextText || '').trim(),
      }),
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
    console.error('Error querying procurement assistant:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Analyzes a bidder's data for fraud risk indicators using AI.
 *
 * @param {Object} bidderData - The bidder profile / submission data to evaluate.
 * @returns {Promise<Object>} The parsed JSON fraud risk analysis response.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function analyzeFraudRisk(bidderData) {
  if (!bidderData) {
    throw new Error('Bidder data payload is required for fraud risk analysis.');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/fraud/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(bidderData),
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
    console.error('Error analyzing fraud risk:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Generates an executive-level procurement audit report from compiled audit data.
 *
 * @param {Object} auditData - The compiled audit data to use for report generation.
 * @returns {Promise<Object>} The parsed JSON executive report response.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function generateExecutiveReport(auditData) {
  if (!auditData) {
    throw new Error('Audit data payload is required for executive report generation.');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/report/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(auditData),
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
    console.error('Error generating executive report:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

export default {
  verifyGSTDocument,
  fetchVerificationHistory,
  analyzeTender,
  classifyDocument,
  fetchTenderHistory,
  compareEntities,
  batchClassifyDocuments,
  verifyBid,
  askProcurementQuestion,
  analyzeFraudRisk,
  generateExecutiveReport,
};
