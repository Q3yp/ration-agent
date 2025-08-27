'use client'

import { useState, useRef, useEffect } from 'react'
import { X, File, Loader2, Paperclip, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getAuthHeaders } from '@/utils/authHeaders'

interface FileUploadProps {
  sessionId: string
  endpoint?: string
  onFileUploaded?: (file: { name: string; size: number; originalName?: string }) => void
  onFilesChange?: (files: UploadedFile[]) => void
}

interface UploadedFile {
  name: string
  size: number
  path: string
}

export default function FileUpload({ sessionId, endpoint = '/api', onFileUploaded, onFilesChange }: FileUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Notify parent component when files change
  useEffect(() => {
    onFilesChange?.(uploadedFiles)
  }, [uploadedFiles, onFilesChange])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length > 0 && !uploading) {
      uploadFiles(files)
    }
  }

  const uploadFiles = async (files: File[]) => {
    setUploading(true)
    setError(null)

    // Filter out files that are already uploaded (by name and size)
    const filesToUpload = files.filter(file => {
      return !uploadedFiles.some(existing =>
        existing.name === file.name && existing.size === file.size
      )
    })

    if (filesToUpload.length === 0) {
      setUploading(false)
      setError('All selected files are already uploaded')
      return
    }

    // Upload all files concurrently and collect results
    const uploadPromises = filesToUpload.map(async (file) => {
      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`${endpoint}/files/upload/${sessionId}`, {
          method: 'POST',
          body: formData,
          headers: getAuthHeaders(),
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

        // Return both the uploaded file and original file info for callback
        return {
          uploadedFile,
          originalName: file.name,
          success: true,
          error: null
        }

      } catch (error: unknown) {
        console.error('Upload error:', error)
        const errorMessage = `Failed to upload ${file.name}: ${error instanceof Error ? error.message : 'Unknown error'}`
        return {
          uploadedFile: null,
          originalName: file.name,
          success: false,
          error: errorMessage
        }
      }
    })

    // Wait for all uploads to complete
    const results = await Promise.all(uploadPromises)

    // Process results
    const successfulUploads = results.filter(result => result.success && result.uploadedFile)
    const errors = results.filter(result => !result.success).map(result => result.error)

    // Update state with all successful uploads at once to avoid race conditions
    if (successfulUploads.length > 0) {
      setUploadedFiles(prev => {
        // Check for duplicates based on filename to avoid adding the same file twice
        const existingNames = new Set(prev.map(f => f.name))
        const newFiles = successfulUploads
          .map(result => result.uploadedFile!)
          .filter(file => !existingNames.has(file.name))
        return [...prev, ...newFiles]
      })

      // Notify parent about successful uploads asynchronously
      setTimeout(() => {
        successfulUploads.forEach(result => {
          onFileUploaded?.({ ...result.uploadedFile!, originalName: result.originalName })
        })
      }, 0)
    }

    // Set error message if any uploads failed
    if (errors.length > 0) {
      setError(errors.join('; '))
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
        headers: getAuthHeaders(),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Delete failed')
      }

      setUploadedFiles(prev => prev.filter(f => f.name !== filename))
    } catch (error: unknown) {
      console.error('Delete error:', error)
      setError(`Failed to delete ${filename}: ${error instanceof Error ? error.message : 'Unknown error'}`)
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
    <div className="space-y-3">
      {/* Compact Upload Button */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-2"
        >
          <Paperclip className="h-4 w-4" />
          {uploading ? '上传中...' : '附加文件'}
          {uploading && <Loader2 className="h-3 w-3 animate-spin" />}
        </Button>
        
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileSelect}
          accept=".txt,.py,.js,.json,.csv,.md,.html,.css,.xml,.yaml,.yml,.xlsx"
          disabled={uploading}
        />
        
        <div className="text-xs text-muted-foreground">
          .txt, .py, .js, .json, .csv, .md, .html, .css, .xml, .yaml, .xlsx (最大 10MB)
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-2 p-2 bg-destructive/10 border border-destructive/20 text-destructive rounded text-sm">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Uploaded Files as Compact Cards */}
      {uploadedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {uploadedFiles.map((file, index) => (
            <div
              key={`${file.name}-${file.size}-${index}`}
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-muted/80 border rounded-full text-sm max-w-xs"
            >
              <File className="h-3 w-3 text-muted-foreground flex-shrink-0" />
              <span className="truncate font-medium">{file.name}</span>
              <span className="text-xs text-muted-foreground flex-shrink-0">
                {formatFileSize(file.size)}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeFile(file.name)}
                className="h-4 w-4 p-0 hover:bg-destructive/20 rounded-full"
                title="移除文件"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}