"use client";

import { useState } from "react";
import { UploadCloud, CheckCircle, FileText } from "lucide-react";
import { motion } from "framer-motion";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const handleVerify = () => {
    if (!file) return;
    setIsVerifying(true);
    
    // Mocking an API call
    setTimeout(() => {
      setIsVerifying(false);
      setResult({
        status: "success",
        gstin: "27AAPFU0939F1ZV",
        entityName: "Acme Corp",
        address: "123 Business Rd, Mumbai",
        isVerified: true,
        matchScore: 98.5
      });
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-3xl space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight sm:text-5xl">
            SIH26100 Evidence Engine
          </h1>
          <p className="mt-4 text-lg text-gray-500">
            Upload a GST PDF document to extract, verify, and evaluate evidence.
          </p>
        </div>

        <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
          <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:bg-gray-50 transition-colors">
            <UploadCloud className="w-12 h-12 text-gray-400 mb-4" />
            <div className="flex text-sm text-gray-600">
              <label
                htmlFor="file-upload"
                className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-blue-500"
              >
                <span>Upload a file</span>
                <input
                  id="file-upload"
                  name="file-upload"
                  type="file"
                  accept=".pdf"
                  className="sr-only"
                  onChange={handleFileChange}
                />
              </label>
              <p className="pl-1">or drag and drop</p>
            </div>
            <p className="text-xs text-gray-500 mt-2">PDF up to 10MB</p>
          </div>

          {file && (
            <div className="mt-4 flex items-center p-4 bg-blue-50 rounded-lg text-blue-700">
              <FileText className="w-5 h-5 mr-3 flex-shrink-0" />
              <span className="font-medium truncate">{file.name}</span>
            </div>
          )}

          <div className="mt-6 flex justify-center">
            <button
              onClick={handleVerify}
              disabled={!file || isVerifying}
              className={`flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white transition-colors
                ${
                  !file || isVerifying
                    ? "bg-gray-400 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-700"
                }
              `}
            >
              {isVerifying ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Verifying...
                </>
              ) : (
                <>
                  <CheckCircle className="w-5 h-5 mr-2" />
                  Verify Document
                </>
              )}
            </button>
          </div>
        </div>

        {result && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gray-900 rounded-xl overflow-hidden shadow-lg border border-gray-800"
          >
            <div className="px-6 py-4 border-b border-gray-800 flex justify-between items-center">
              <h3 className="text-lg font-medium text-white">Verification Results</h3>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-900 text-green-300">
                Processed
              </span>
            </div>
            <div className="p-6">
              <pre className="text-sm text-green-400 overflow-x-auto font-mono">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
