'use client'

import { Message, ArtifactData, getArtifactMetadata, getRoleTransitionMetadata, getToolMetadata, getFileExportMetadata, getAnalysisMetadata, getFormulationMetadata, getCalculationMetadata } from '@/types/chat'
import {
  Settings,
  CheckCircle,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  User,
  File,
  CornerDownRight,
  Calculator
} from 'lucide-react'
import Image from 'next/image'
import { formatTimestamp } from '@/utils/formatTime'
import { getRoleInfo, getToolName } from '@/utils/roleMapping'
import MarkdownMessage from './MarkdownMessage'
import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import { useI18n } from '@/contexts/I18nContext'

interface MessageBubbleProps {
  message: Message
  onArtifactOpen?: (artifactData: ArtifactData) => void
  onFileDownload?: (filename: string, sessionId: string) => void
  sessionId?: string
}

export default function MessageBubble({ message, onArtifactOpen, onFileDownload, sessionId }: MessageBubbleProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const { t } = useI18n()

  // Parse file upload tags from user message content
  const parseFileUploads = (content: string) => {
    const fileUploadRegex = /\[FILE_UPLOAD\](.*?)\[\/FILE_UPLOAD\]/g
    const fileUploads: string[] = []
    let match

    while ((match = fileUploadRegex.exec(content)) !== null) {
      fileUploads.push(match[1])
    }

    const cleanContent = content.replace(fileUploadRegex, '').trim()
    return { fileUploads, cleanContent }
  }

  const renderUserMessage = () => {
    const { fileUploads, cleanContent } = parseFileUploads(message.content)

    return (
      <div className="flex justify-end items-start gap-2">
        <div className="max-w-[80%] space-y-2">
          {/* File Uploads */}
          {fileUploads.length > 0 && (
            <div className="flex justify-end">
              <Card className="bg-blue-50 border-blue-200">
                <CardContent className="p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <File className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium text-blue-600">
                      {t('fileUpload.fileUploaded')} ({t('fileUpload.filesCount', { count: fileUploads.length })})
                    </span>
                  </div>
                  <div className="space-y-1">
                    {fileUploads.map((fileName, index) => (
                      <div key={`${fileName}-${index}`} className="flex items-center gap-2 text-sm text-blue-700">
                        <File className="h-3 w-3" />
                        <span className="truncate max-w-[200px]">{fileName}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Message Content */}
          {cleanContent && (
            <Card className="bg-primary text-primary-foreground">
              <CardContent className="p-3">
                <div className="whitespace-pre-wrap">{cleanContent}</div>
                <div className="text-xs opacity-70 mt-2">
                  {formatTimestamp(message.timestamp)}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        <Avatar className="w-8 h-8">
          <AvatarFallback>
            <User className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      </div>
    )
  }

  const renderAgentMessage = () => (
    <div className="flex justify-start items-start gap-2">
      <Avatar className="w-8 h-8">
        <AvatarFallback className="bg-transparent">
          <Image
            src="/agent_icon.png"
            alt="Agent"
            width={32}
            height={32}
            className="w-full h-full object-contain translate-y-[2px]"
          />
        </AvatarFallback>
      </Avatar>
      <Card className="max-w-[80%] min-w-0 overflow-hidden bg-card">
        <CardContent className="p-3">
          <MarkdownMessage
            content={message.content}
            isStreaming={message.metadata?.is_streaming || false}
          />
          <div className="text-xs text-muted-foreground mt-2">
            {formatTimestamp(message.timestamp)}
          </div>
        </CardContent>
      </Card>
    </div>
  )

  const renderToolCall = () => {
    const toolMeta = getToolMetadata(message)

    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <Settings className="h-4 w-4 text-gray-600" />
        </div>
        <Card className="max-w-[80%] min-w-0 overflow-hidden bg-gray-50 border-gray-200">
          <CardContent className="p-3">
            <div
              className="flex items-center justify-between cursor-pointer"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              <div className="flex items-center min-w-0">
                <ChevronRight className={cn(
                  "h-4 w-4 mr-1 transition-transform flex-shrink-0",
                  isExpanded && "rotate-90"
                )} />
                <span className="font-semibold truncate">
                  {getToolName(toolMeta?.tool_name || message.content.replace('Executing ', ''))}
                </span>
              </div>
              <Badge variant="secondary" className="text-xs flex-shrink-0 ml-2">
                {formatTimestamp(message.timestamp)}
              </Badge>
            </div>

            {/* Expandable tool arguments */}
            {isExpanded && toolMeta?.tool_args && Object.keys(toolMeta.tool_args).length > 0 && (
              <div className="mt-3 bg-gray-100 p-3 rounded-md text-xs max-h-64 overflow-auto">
                <strong>参数:</strong>
                <pre className="mt-1 whitespace-pre-wrap font-mono break-all">
                  {JSON.stringify(toolMeta.tool_args, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderToolResult = () => {
    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <CheckCircle className="h-4 w-4 text-green-600" />
        </div>
        <Card className="max-w-[80%] min-w-0 overflow-hidden border-green-200 bg-green-50">
          <CardContent className="p-3">
            <div
              className="flex items-center justify-between cursor-pointer"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              <div className="flex items-center min-w-0">
                <ChevronRight className={cn(
                  "h-4 w-4 mr-1 transition-transform flex-shrink-0 text-green-600",
                  isExpanded && "rotate-90"
                )} />
                <span className="text-sm text-green-700">
                  工具结果
                </span>
              </div>
              <Badge variant="outline" className="text-xs text-green-600 flex-shrink-0 ml-2">
                {formatTimestamp(message.timestamp)}
              </Badge>
            </div>

            {/* Expandable content */}
            {isExpanded && (
              <div className="mt-3 bg-green-100 p-3 rounded-md text-xs max-h-64 overflow-auto">
                <pre className="whitespace-pre-wrap font-mono break-all">
                  {message.content}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderRoleTransition = () => {
    const roleTransitionMeta = getRoleTransitionMetadata(message)
    const roleInfo = getRoleInfo(roleTransitionMeta?.to_role || '')
    const RoleIcon = roleInfo.icon

    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <CornerDownRight className="h-4 w-4 text-gray-500" />
        </div>
        <Card
          className={cn("max-w-[80%] min-w-0 overflow-hidden", !roleInfo.customStyles && roleInfo.bgColor)}
          style={roleInfo.customStyles ? {
            backgroundColor: roleInfo.customStyles.backgroundColor,
            borderColor: roleInfo.customStyles.borderColor,
            borderWidth: '1px'
          } : undefined}
        >
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <RoleIcon
                className={cn("h-4 w-4", !roleInfo.customStyles && roleInfo.color)}
                style={roleInfo.customStyles ? { color: roleInfo.customStyles.color } : undefined}
              />
              <span
                className={cn("font-medium", !roleInfo.customStyles && roleInfo.color)}
                style={roleInfo.customStyles ? { color: roleInfo.customStyles.color } : undefined}
              >
                {message.content}
              </span>
            </div>

            <div
              className={cn("text-xs mt-1", !roleInfo.customStyles && roleInfo.color.replace('700', '600'))}
              style={roleInfo.customStyles ? { color: roleInfo.customStyles.color, opacity: 0.7 } : undefined}
            >
              {formatTimestamp(message.timestamp)}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderArtifact = () => {
    const artifactMeta = getArtifactMetadata(message)
    if (!artifactMeta?.html_content) return null

    const artifactData: ArtifactData = {
      title: artifactMeta.title || message.content,
      description: artifactMeta.description || '',
      html_content: artifactMeta.html_content
    }

    return (
      <div className="flex justify-start items-start gap-2 my-4">
        <div className="w-8 h-8 flex items-center justify-center">
          <div className="w-2 h-2 bg-blue-400 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.6)]"></div>
        </div>

        {/* Ultra Fancy Holographic Card */}
        <div className="relative max-w-[90%] min-w-0 cursor-pointer" onClick={() => onArtifactOpen?.(artifactData)}>
          {/* Background Glow */}
          <div className="absolute -inset-1 bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 rounded-3xl opacity-50 blur-sm"></div>

          {/* Main Glass Card */}
          <div className="relative bg-white/15 backdrop-blur-xl border border-white/30 rounded-3xl p-6">

            {/* Holographic Overlay */}
            <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-blue-200/30 via-transparent to-purple-200/30 opacity-60"></div>

            {/* Floating Orbs */}
            <div className="absolute top-2 right-4 w-12 h-12 bg-gradient-to-br from-blue-300/40 to-purple-300/40 rounded-full blur-xl"></div>
            <div className="absolute bottom-4 left-2 w-8 h-8 bg-gradient-to-br from-indigo-300/30 to-blue-300/30 rounded-full blur-lg"></div>
            <div className="absolute top-1/2 left-1/4 w-6 h-6 bg-gradient-to-br from-purple-300/20 to-blue-300/20 rounded-full blur-md"></div>

            {/* Content Container */}
            <div className="relative z-10 flex items-center gap-5">

              {/* Ultra Fancy Artifact Icon */}
              <div className="relative">
                {/* Icon Glow Ring */}
                <div className="absolute -inset-2 bg-gradient-to-r from-blue-400 to-purple-400 rounded-full opacity-60 blur-sm"></div>

                {/* Icon Container */}
                <div className="relative w-20 h-20 bg-gradient-to-br from-white/40 to-white/20 backdrop-blur-md border border-white/40 rounded-2xl flex items-center justify-center">
                  {/* Inner Glow */}
                  <div className="absolute inset-2 bg-gradient-to-br from-blue-100/50 to-purple-100/50 rounded-xl"></div>

                  {/* HTML Icon */}
                  <div className="relative z-10 text-3xl filter drop-shadow-[0_2px_8px_rgba(59,130,246,0.5)]">
                    📄
                  </div>

                  {/* Sparkle Effect */}
                  <div className="absolute top-1 right-1 w-2 h-2 bg-white rounded-full opacity-90"></div>
                </div>
              </div>

              {/* Content Section */}
              <div className="flex-1 min-w-0">
                {/* Title with Holographic Text */}
                <div className="text-xl font-bold bg-gradient-to-r from-gray-800 via-blue-700 to-purple-700 bg-clip-text text-transparent mb-2 truncate filter drop-shadow-sm">
                  {artifactData.title}
                </div>

                {/* Open Label - Floating Pill */}
                <div className="relative inline-flex items-center">
                  <div className="absolute -inset-1 bg-gradient-to-r from-blue-400 to-purple-400 rounded-full opacity-70 blur-sm"></div>
                  <div className="relative bg-gradient-to-r from-blue-500 to-purple-500 text-white px-4 py-2 rounded-full text-sm font-bold shadow-lg">
                    <span className="flex items-center gap-2">
                      {t('artifact.viewDynamicContent')}
                    </span>
                  </div>
                </div>

                {/* Description */}
                {artifactData.description && (
                  <div className="mt-2 inline-block bg-white/20 backdrop-blur-sm border border-white/30 px-3 py-1 rounded-full text-xs font-medium text-gray-600">
                    {artifactData.description}
                  </div>
                )}
              </div>

            </div>

            {/* Bottom Section */}
            <div className="relative z-10 mt-4 pt-3 border-t border-white/30">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-gray-500">
                  <div className="w-2 h-2 bg-gradient-to-r from-blue-400 to-purple-400 rounded-full"></div>
                  {t('artifact.htmlDynamicContent')}
                </div>
                <div className="text-gray-400 bg-white/20 px-2 py-1 rounded-full backdrop-blur-sm border border-white/20">
                  {formatTimestamp(message.timestamp)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderFileExport = () => {
    const fileExportMeta = getFileExportMetadata(message)
    if (!fileExportMeta?.filename) return null

    const handleDownload = () => {
      if (onFileDownload && sessionId && fileExportMeta.filename) {
        onFileDownload(fileExportMeta.filename, sessionId)
      }
    }

    const getFileIcon = (fileType: string) => {
      switch (fileType) {
        case 'excel':
          return '📊'
        case 'csv':
          return '📈'
        case 'json':
          return '📄'
        default:
          return '📁'
      }
    }

    return (
      <div className="flex justify-start items-start gap-2 my-4">
        <div className="w-8 h-8 flex items-center justify-center">
          <div className="w-2 h-2 bg-emerald-400 rounded-full shadow-[0_0_8px_rgba(52,211,153,0.6)]"></div>
        </div>

        {/* Ultra Fancy Holographic Card */}
        <div className="relative max-w-[90%] min-w-0 cursor-pointer" onClick={handleDownload}>
          {/* Background Glow */}
          <div className="absolute -inset-1 bg-gradient-to-r from-emerald-400 via-green-400 to-teal-400 rounded-3xl opacity-50 blur-sm"></div>

          {/* Main Glass Card */}
          <div className="relative bg-white/15 backdrop-blur-xl border border-white/30 rounded-3xl p-6">

            {/* Holographic Overlay */}
            <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-emerald-200/30 via-transparent to-teal-200/30 opacity-60"></div>

            {/* Floating Orbs */}
            <div className="absolute top-2 right-4 w-12 h-12 bg-gradient-to-br from-emerald-300/40 to-teal-300/40 rounded-full blur-xl"></div>
            <div className="absolute bottom-4 left-2 w-8 h-8 bg-gradient-to-br from-green-300/30 to-emerald-300/30 rounded-full blur-lg"></div>
            <div className="absolute top-1/2 left-1/4 w-6 h-6 bg-gradient-to-br from-teal-300/20 to-emerald-300/20 rounded-full blur-md"></div>

            {/* Content Container */}
            <div className="relative z-10 flex items-center gap-5">

              {/* Ultra Fancy File Icon */}
              <div className="relative">
                {/* Icon Glow Ring */}
                <div className="absolute -inset-2 bg-gradient-to-r from-emerald-400 to-teal-400 rounded-full opacity-60 blur-sm"></div>

                {/* Icon Container */}
                <div className="relative w-20 h-20 bg-gradient-to-br from-white/40 to-white/20 backdrop-blur-md border border-white/40 rounded-2xl flex items-center justify-center">
                  {/* Inner Glow */}
                  <div className="absolute inset-2 bg-gradient-to-br from-emerald-100/50 to-teal-100/50 rounded-xl"></div>

                  {/* File Icon */}
                  <div className="relative z-10 text-3xl filter drop-shadow-[0_2px_8px_rgba(52,211,153,0.5)]">
                    {getFileIcon(fileExportMeta.file_type || '')}
                  </div>

                  {/* Sparkle Effect */}
                  <div className="absolute top-1 right-1 w-2 h-2 bg-white rounded-full opacity-90"></div>
                </div>
              </div>

              {/* Content Section */}
              <div className="flex-1 min-w-0">
                {/* Filename with Holographic Text */}
                <div className="text-xl font-bold bg-gradient-to-r from-gray-800 via-emerald-700 to-teal-700 bg-clip-text text-transparent mb-2 truncate filter drop-shadow-sm">
                  {fileExportMeta.filename}
                </div>

                {/* Download Label - Floating Pill */}
                <div className="relative inline-flex items-center">
                  <div className="absolute -inset-1 bg-gradient-to-r from-emerald-400 to-teal-400 rounded-full opacity-70 blur-sm"></div>
                  <div className="relative bg-gradient-to-r from-emerald-500 to-teal-500 text-white px-4 py-2 rounded-full text-sm font-bold shadow-lg">
                    <span className="flex items-center gap-2">
                      {t('fileExport.downloadRecipe')}
                    </span>
                  </div>
                </div>

                {/* File Type Badge */}
                <div className="mt-2 inline-block bg-white/20 backdrop-blur-sm border border-white/30 px-3 py-1 rounded-full text-xs font-medium text-gray-600">
                  {t('fileExport.format', { type: fileExportMeta.file_type?.toUpperCase() || '' })}
                </div>

                {/* Description Button */}
                {fileExportMeta.description && (
                  <div
                    onClick={(e) => {
                      e.stopPropagation()
                      if (onArtifactOpen) {
                        // First convert literal \n to actual newlines (fix double-escaped JSON)
                        // Then escape HTML to prevent XSS, but preserve formatting
                        const escapedDescription = (fileExportMeta.description || '')
                          .replace(/\\n/g, '\n')  // Convert literal \n to actual newlines
                          .replace(/&/g, '&amp;')
                          .replace(/</g, '&lt;')
                          .replace(/>/g, '&gt;')
                          .replace(/"/g, '&quot;')
                          .replace(/'/g, '&#039;')

                        const htmlContent = `
                          <div style="font-family: system-ui, -apple-system, sans-serif; padding: 24px; line-height: 1.6; color: #374151; max-width: 800px; margin: 0 auto;">
                            <h2 style="color: #059669; margin-bottom: 20px; font-size: 24px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                              <span>💡</span> ${t('fileExport.recipeSuggestion')}
                            </h2>
                            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 20px; font-size: 15px;">
                              <pre style="white-space: pre-wrap; font-family: inherit; margin: 0; line-height: 1.6;">${escapedDescription}</pre>
                            </div>
                          </div>
                        `
                        onArtifactOpen({
                          title: `${t('artifact.recipeSuggestionPrefix')}${fileExportMeta.filename}`,
                          description: t('artifact.recipeAnalysisTitle'),
                          html_content: htmlContent
                        })
                      }
                    }}
                    className="mt-3 w-full bg-white/30 hover:bg-white/40 backdrop-blur-md border border-white/40 p-2.5 rounded-xl text-sm text-emerald-900 font-semibold transition-all cursor-pointer flex items-center justify-center gap-2 shadow-sm hover:shadow-md active:scale-[0.98]"
                  >
                    <span>{t('artifact.viewSuggestion')}</span>
                  </div>
                )}
              </div>

            </div>

            {/* Bottom Section */}
            <div className="relative z-10 mt-4 pt-3 border-t border-white/30">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-gray-500">
                  <div className="w-2 h-2 bg-gradient-to-r from-emerald-400 to-teal-400 rounded-full"></div>
                  {t('fileExport.readyDownload')}
                </div>
                <div className="text-gray-400 bg-white/20 px-2 py-1 rounded-full backdrop-blur-sm border border-white/20">
                  {formatTimestamp(message.timestamp)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderAnalysis = () => {
    const analysisMeta = getAnalysisMetadata(message)
    const isComplete = message.type === 'analysis_complete'
    const operations = analysisMeta?.operations || []

    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
        </div>
        <Card className="w-full sm:min-w-[300px] sm:max-w-[500px] md:min-w-[400px] md:max-w-[600px] bg-blue-50 border-blue-200">
          <CardContent className="p-3">
            {isComplete ? (
              // Completed state - same style as TypingIndicator, show expandable list
              <div className="space-y-2">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setIsExpanded(!isExpanded)}
                >
                  <div className="flex items-center space-x-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                    <span className="text-muted-foreground text-sm ml-2">
                      {message.content}
                    </span>
                  </div>
                  {operations.length > 0 && (
                    <div className="flex items-center">
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </div>
                  )}
                </div>

                {/* Expandable operations list */}
                {isExpanded && operations.length > 0 && (
                  <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                    {operations.map((operation, index) => (
                      <div
                        key={`${operation}-${index}`}
                        className="flex items-center space-x-1 text-xs text-gray-500"
                      >
                        <div className="w-1 h-1 bg-gray-400 rounded-full"></div>
                        <span className="ml-2">{operation}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              // Non-complete states (start/update) - simple display
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                <span className="text-muted-foreground text-sm ml-2">
                  {message.content}
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderFormulation = () => {
    const formulationMeta = getFormulationMetadata(message)
    const isComplete = message.type === 'formulation_complete'
    const operations = formulationMeta?.operations || []

    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <div className="w-2 h-2 bg-green-400 rounded-full"></div>
        </div>
        <Card className="w-full sm:min-w-[300px] sm:max-w-[500px] md:min-w-[400px] md:max-w-[600px] bg-green-50 border-green-200">
          <CardContent className="p-3">
            {isComplete ? (
              // Completed state - same style as FormulationIndicator, show expandable list
              <div className="space-y-2">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setIsExpanded(!isExpanded)}
                >
                  <div className="flex items-center space-x-1">
                    <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                    <span className="text-muted-foreground text-sm ml-2">
                      {message.content}
                    </span>
                  </div>
                  {operations.length > 0 && (
                    <div className="flex items-center">
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </div>
                  )}
                </div>

                {/* Expandable operations list with structured data */}
                {isExpanded && operations.length > 0 && (
                  <div className="mt-2 space-y-2 max-h-60 overflow-y-auto">
                    {operations.map((operation, index) => (
                      <div
                        key={`${operation}-${index}`}
                        className="flex items-start space-x-2 text-xs"
                      >
                        <div className="w-1 h-1 bg-green-400 rounded-full mt-2"></div>
                        <div className="flex-1">
                          <div className="text-gray-700 font-medium">{operation}</div>
                          {/* Show structured data if available */}
                          {formulationMeta?.formulation_results && Object.keys(formulationMeta.formulation_results).length > 0 && index === operations.length - 1 && (
                            <div className="mt-1 text-gray-500 text-xs">
                              <div>配方结果已生成</div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              // Non-complete states (start/update) - simple display
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-muted-foreground text-sm ml-2">
                  {message.content}
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderCalculation = () => {
    const calcMeta = getCalculationMetadata(message)
    const expression = calcMeta?.expression || ''
    const allResults = calcMeta?.all_results || []
    const locale = calcMeta?.preferred_language || 'zh-CN'
    const isEnglish = locale === 'en-US'
    const label = isEnglish ? 'Calculate' : '计算'

    const expressions = expression.split('\n').filter(e => e.trim())

    // Debug: log what we received
    console.log('Calculation debug:', { expressions, allResults })

    // Only render if we have matching results for all expressions
    if (allResults.length !== expressions.length) {
      return null
    }

    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <Calculator className="h-4 w-4 text-blue-600" />
        </div>
        <Card className="max-w-[80%] min-w-0 overflow-hidden bg-blue-50 border-blue-200">
          <CardContent className="p-2">
            <div className="font-mono text-sm">
              <div className="text-gray-600 text-xs mb-2">{label}:</div>
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {expressions.map((expr, idx) => (
                  <div key={idx} className="flex items-start justify-between gap-3 text-xs">
                    <span className="text-gray-700 font-mono text-left">{expr}</span>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <span className="text-blue-500">→</span>
                      <span className="font-semibold text-blue-900 font-mono">{allResults[idx]}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Route to appropriate renderer based on message type
  switch (message.type) {
    case 'user':
      return renderUserMessage()
    case 'agent':
      return renderAgentMessage()
    case 'tool_call':
      return renderToolCall()
    case 'tool_result':
      return renderToolResult()
    case 'role_transition':
      return renderRoleTransition()
    case 'artifact':
      return renderArtifact()
    case 'file_export':
      return renderFileExport()
    case 'analysis_start':
    case 'analysis_update':
    case 'analysis_complete':
      return renderAnalysis()
    case 'formulation_start':
    case 'formulation_update':
    case 'formulation_complete':
      return renderFormulation()
    case 'calculation':
      return renderCalculation()
    default:
      // Unknown message type fallback
      return (
        <div className="flex justify-center">
          <Card className="max-w-md bg-muted">
            <CardContent className="p-3 text-center">
              <div className="text-xs">Unknown message type: {message.type}</div>
            </CardContent>
          </Card>
        </div>
      )
  }
}
