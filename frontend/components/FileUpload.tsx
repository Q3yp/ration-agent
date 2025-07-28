'use client'

import { useState, useRef } from 'react'
import { DocumentArrowUpIcon, XMarkIcon, DocumentIcon } from '@heroicons/react/24/outline'

interface FileUploadProps {
  sessionId: string
  endpoint?: string
  onFileUploaded?: (file: { name: string; size: number }) => void
}

interface UploadedFile {
  name: string
  size: number
  path: string
}

export default function FileUpload({ sessionId, endpoint = 'http://localhost:8000', onFileUploaded }: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      uploadFiles(files)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length > 0) {
      uploadFiles(files)
    }
  }

  const uploadFiles = async (files: File[]) => {
    setUploading(true)
    setError(null)

    for (const file of files) {
      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`${endpoint}/files/upload/${sessionId}`, {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Upload failed')
        }

        const result = await response.json()
        const uploadedFile: UploadedFile = {
          name: result.filename,
          size: result.size,
          path: result.path
        }

        setUploadedFiles(prev => [...prev, uploadedFile])
        onFileUploaded?.(uploadedFile)

      } catch (error: any) {
        console.error('Upload error:', error)
        setError(`Failed to upload ${file.name}: ${error.message}`)
      }
    }

    setUploading(false)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const removeFile = async (filename: string) => {
    try {
      const response = await fetch(`${endpoint}/files/delete/${sessionId}/${filename}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Delete failed')
      }

      setUploadedFiles(prev => prev.filter(f => f.name !== filename))
    } catch (error: any) {
      console.error('Delete error:', error)
      setError(`Failed to delete ${filename}: ${error.message}`)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          isDragOver
            ? 'border-primary-500 bg-primary-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <DocumentArrowUpIcon className="h-8 w-8 mx-auto text-gray-400 mb-2" />
        <p className="text-sm text-gray-600 mb-2">
          拖放文件到此处，或{' '}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-primary-500 hover:text-primary-600 underline"
            disabled={uploading}
          >
            浏览文件
          </button>
        </p>
        <p className="text-xs text-gray-500">
          支持格式：.txt, .py, .js, .json, .csv, .md, .html, .css, .xml, .yaml, .xlsx (最大 10MB)
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileSelect}
          accept=".txt,.py,.js,.json,.csv,.md,.html,.css,.xml,.yaml,.yml,.xlsx"
          disabled={uploading}
        />
      </div>

      {/* Upload Status */}
      {uploading && (
        <div className="mt-3 text-sm text-blue-600 flex items-center">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
          正在上传文件...
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-3 p-2 bg-red-100 border border-red-400 text-red-700 rounded text-sm">
          {error}
        </div>
      )}

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">已上传文件：</h4>
          <div className="space-y-2">
            {uploadedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-2 bg-white border border-gray-200 rounded"
              >
                <div className="flex items-center">
                  <DocumentIcon className="h-4 w-4 text-gray-400 mr-2" />
                  <span className="text-sm text-gray-700">{file.name}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    ({formatFileSize(file.size)})
                  </span>
                </div>
                <button
                  onClick={() => removeFile(file.name)}
                  className="text-red-500 hover:text-red-700 p-1"
                  title="删除文件"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}