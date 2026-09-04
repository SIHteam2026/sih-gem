/**
 * API service for verifying GST documents against backend endpoints.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

/**
 * Verifies an uploaded GST PDF document.
 * 
 * @param {File | Blob} file - The GST PDF file to verify.
 * @returns {Promise<any>} The parsed JSON response from the server.
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
 * @returns {Promise<any[]>} The parsed JSON array of historical records.
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
 * @returns {Promise<any>} The parsed JSON response from the server.
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
 * @returns {Promise<any>} The parsed JSON response from the server.
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
 * @returns {Promise<any>} The parsed JSON response comparing the entities.
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
 * @returns {Promise<any>} The parsed JSON response from the server.
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
 * @returns {Promise<any>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function verifyBid(tenderFile, bidderFile, requirementId) {
  if (!tenderFile || !bidderFile || !requirementId) {
    throw new Error('Tender file, bidder file(s), and requirement ID are all required to verify a bid.');
  }

  const formData = new FormData();
  formData.append('tender_file', tenderFile);
  formData.append('requirement_id', String(requirementId));

  if (Array.isArray(bidderFile) || (typeof FileList !== 'undefined' && bidderFile instanceof FileList)) {
    const fileList = Array.from(bidderFile);
    fileList.forEach((file) => {
      formData.append('bidder_files', file);
    });
    if (fileList.length > 0) {
      formData.append('bidder_file', fileList[0]);
    }
  } else {
    formData.append('bidder_file', bidderFile);
    formData.append('bidder_files', bidderFile);
  }

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
 * Extracts structured data, tables, and raw text from one or more documents (PDF, CSV, DOCX, XLSX, TXT).
 * 
 * @param {File[] | FileList} files - List of document files to extract data from.
 * @returns {Promise<any>} The parsed JSON response containing extraction records.
 */
export async function extractDocuments(files) {
  if (!files || (Array.isArray(files) && files.length === 0)) {
    throw new Error('At least one document file is required for extraction.');
  }

  const formData = new FormData();
  const fileArray = Array.isArray(files) ? files : Array.from(files);
  fileArray.forEach((f) => formData.append('files', f));

  try {
    const response = await fetch(`${API_BASE_URL}/api/documents/extract`, {
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
        // Fallback
      }
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error('Error extracting document data:', error);
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
 * @returns {Promise<any>} The parsed JSON response from the server.
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
 * @returns {Promise<any>} The parsed JSON fraud risk analysis response.
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
 * @returns {Promise<any>} The parsed JSON executive report response.
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

/**
 * Generates a formal clarification / shortfall notice for non-compliant bidders.
 *
 * @param {Object} complianceData - Data regarding bidder compliance and missing documents.
 * @returns {Promise<any>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function generateShortfallNotice(complianceData) {
  if (!complianceData) {
    throw new Error('Compliance data payload is required to generate a shortfall notice.');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/clarification/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(complianceData),
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
    console.error('Error generating shortfall notice:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Generates a formal Award of Contract document for the winning bidder.
 *
 * @param {Object} tenderData - Details of the tender document and requirements.
 * @param {Object} winnerData - Details of the winning bidder and offer.
 * @returns {Promise<any>} The parsed JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function generateAwardContract(tenderData, winnerData) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/contract/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tender_data: tenderData || {},
        winner_data: winnerData || {},
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
    console.error('Error generating award contract:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Performs complete end-to-end master evaluation of a tender and bidder documents in a single call.
 *
 * @param {File} tenderFile - The tender PDF file.
 * @param {File} [bidderFile] - The bidder PDF/evidence file.
 * @returns {Promise<any>} The unified master evaluation JSON response from the server.
 * @throws {Error} Clear error message if validation, network request, or server response fails.
 */
export async function evaluateComplete(tenderFile, bidderFile) {
  if (!tenderFile) {
    throw new Error('Tender document file is required for complete evaluation.');
  }

  const formData = new FormData();
  formData.append('tender_file', tenderFile);
  if (bidderFile) {
    formData.append('bidder_file', bidderFile);
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/evaluate/complete`, {
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
    console.error('Error executing complete evaluation:', error);
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`Network error: Unable to connect to the backend server at ${API_BASE_URL}. Please ensure the server is running.`);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Ingests a structured simulated GeM procurement package via the Mock-GeM adapter.
 * 
 * @param {Object} payload - The simulated GeM procurement package.
 * @returns {Promise<any>} The canonical ProcurementIngestionResult.
 */
export async function ingestMockGeMPackage(payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/ingest/mock-gem`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message || errorBody.error)) {
          errorMessage = errorBody.detail || errorBody.message || errorBody.error;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error('Error in Mock-GeM package ingestion:', error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Ingests the pre-packaged synthetic CPCL Water Quality Monitoring procurement (DEMO/CPCL/WQM/2026/017).
 * 
 * @returns {Promise<any>} The canonical ProcurementIngestionResult.
 */
export async function ingestMockGeMDemo() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/ingest/mock-gem/demo`, {
      method: 'POST',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message || errorBody.error)) {
          errorMessage = errorBody.detail || errorBody.message || errorBody.error;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error('Error in Mock-GeM demo ingestion:', error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Uploads a simulated GeM ZIP package containing metadata.json and procurement documents.
 * 
 * @param {File | Blob} zipFile - The ZIP package file.
 * @returns {Promise<any>} The canonical ProcurementIngestionResult.
 */
export async function ingestMockGeMZip(zipFile) {
  if (!zipFile) {
    throw new Error('A valid ZIP package file is required.');
  }

  const formData = new FormData();
  formData.append('file', zipFile);

  try {
    const response = await fetch(`${API_BASE_URL}/api/ingest/mock-gem/zip`, {
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
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error('Error in Mock-GeM ZIP package ingestion:', error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches paginated procurement workspace summaries.
 * 
 * @param {number} limit - Max records to return.
 * @param {number} offset - Offset index.
 * @returns {Promise<any>} Object containing procurements array, total, limit, and offset.
 */
export async function fetchProcurements(limit = 50, offset = 0) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/procurements?limit=${limit}&offset=${offset}`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching procurement list:', error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches single procurement workspace detail.
 * 
 * @param {string} procurementId - Procurement UUID.
 * @returns {Promise<any>} Procurement detail object.
 */
export async function fetchProcurementDetail(procurementId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/procurements/${encodeURIComponent(procurementId)}`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching procurement detail for ${procurementId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches tender workspace detail by tender ID.
 * 
 * @param {string} tenderId - Tender UUID.
 * @returns {Promise<any>} Tender workspace detail object.
 */
export async function fetchTenderDetail(tenderId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tenders/${encodeURIComponent(tenderId)}`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching tender detail for ${tenderId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches submission detail by submission ID.
 * 
 * @param {string} submissionId - Bid submission UUID.
 * @returns {Promise<any>} Submission detail object.
 */
export async function fetchSubmissionDetail(submissionId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/submissions/${encodeURIComponent(submissionId)}`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching submission detail for ${submissionId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches bidder profile detail by bidder ID.
 * 
 * @param {string} bidderId - Bidder UUID.
 * @returns {Promise<any>} Bidder detail object.
 */
export async function fetchBidderDetail(bidderId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/bidders/${encodeURIComponent(bidderId)}`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching bidder detail for ${bidderId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches canonical structured requirements for a specific tender.
 * 
 * @param {string} tenderId - Tender UUID.
 * @returns {Promise<any[]>} List of TenderRequirement objects.
 */
export async function fetchTenderRequirements(tenderId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tenders/${encodeURIComponent(tenderId)}/requirements`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching requirements for tender ${tenderId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches bidder submissions for a specific tender.
 * 
 * @param {string} tenderId - Tender UUID.
 * @returns {Promise<any[]>} List of SubmissionSummary objects.
 */
export async function fetchTenderSubmissions(tenderId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tenders/${encodeURIComponent(tenderId)}/submissions`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching submissions for tender ${tenderId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches evaluation contract for a specific tender.
 * 
 * @param {string} tenderId - Tender UUID.
 * @returns {Promise<any>} TenderEvaluationContract object.
 */
export async function fetchTenderEvaluationContract(tenderId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tenders/${encodeURIComponent(tenderId)}/evaluation-contract`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching evaluation contract for tender ${tenderId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Starts the processing lifecycle pipeline for a procurement workspace.
 * 
 * @param {string} procurementId - Procurement workspace UUID.
 * @param {boolean} [force=false] - Force re-processing flag.
 * @returns {Promise<Object>} Start processing response object.
 */
export async function startProcurementProcessing(procurementId, force = false) {
  try {
    const url = `${API_BASE_URL}/api/procurements/${encodeURIComponent(procurementId)}/process?force=${Boolean(force)}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error starting processing for procurement ${procurementId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Fetches the processing lifecycle status of a procurement workspace.
 * 
 * @param {string} procurementId - Procurement workspace UUID.
 * @returns {Promise<Object>} Processing status object.
 */
export async function getProcurementProcessingStatus(procurementId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/procurements/${encodeURIComponent(procurementId)}/processing-status`, {
      method: 'GET',
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching processing status for procurement ${procurementId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * Evaluates a bidder submission against canonical tender requirements.
 * Calls POST /api/evaluate/complete with canonical submission_id and tender reference.
 * 
 * @param {string} submissionId - Bid submission UUID.
 * @param {string} [tenderId] - Optional tender UUID or reference.
 * @param {string} [bidderName] - Optional legal bidder name.
 * @returns {Promise<any>} Submission evaluation result object.
 */
export async function evaluateSubmission(submissionId, tenderId = '', bidderName = '') {
  if (!submissionId) {
    throw new Error('A valid submission ID is required to evaluate a submission.');
  }

  const payload = {
    submission_id: submissionId,
    tender_id: tenderId || 'TENDER-CANONICAL',
    bidder_name: bidderName || 'Bidder Entity',
  };

  try {
    const response = await fetch(`${API_BASE_URL}/api/evaluate/complete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let errorMessage = `Server error (${response.status}): ${response.statusText}`;
      try {
        const errorBody = await response.json();
        if (errorBody && (errorBody.detail || errorBody.message)) {
          errorMessage = errorBody.detail || errorBody.message;
        }
      } catch {}
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Error evaluating submission ${submissionId}:`, error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

export const fetchSubmissionEvaluation = evaluateSubmission;

// Canonical alias exports for convenience
export const getProcurements = fetchProcurements;
export const getProcurement = fetchProcurementDetail;
export const getTender = fetchTenderDetail;
export const getTenderRequirements = fetchTenderRequirements;
export const getTenderSubmissions = fetchTenderSubmissions;
export const getSubmission = fetchSubmissionDetail;
export const getBidder = fetchBidderDetail;
export const getTenderEvaluationContract = fetchTenderEvaluationContract;

const api = {
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
  generateShortfallNotice,
  generateAwardContract,
  evaluateComplete,
  ingestMockGeMPackage,
  ingestMockGeMDemo,
  ingestMockGeMZip,
  fetchProcurements,
  fetchProcurementDetail,
  fetchTenderDetail,
  fetchSubmissionDetail,
  fetchBidderDetail,
  fetchTenderRequirements,
  fetchTenderSubmissions,
  fetchTenderEvaluationContract,
  evaluateSubmission,
  fetchSubmissionEvaluation,
  getProcurements,
  getProcurement,
  getTender,
  getTenderRequirements,
  getTenderSubmissions,
  getSubmission,
  getBidder,
  getTenderEvaluationContract,
  startProcurementProcessing,
  getProcurementProcessingStatus,
};

export default api;



