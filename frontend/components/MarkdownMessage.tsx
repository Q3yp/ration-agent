'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
// Temporarily simplify to debug
// import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
// import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface MarkdownMessageProps {
  content: string
  isStreaming?: boolean
}

export default function MarkdownMessage({ content, isStreaming = false }: MarkdownMessageProps) {
  // Add cursor for streaming effect
  const displayContent = isStreaming ? `${content}▋` : content

  return (
    <div className="prose prose-sm max-w-none prose-slate dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const isInline = !className || !match
            return isInline ? (
              <code className="bg-muted px-1 py-0.5 rounded text-sm font-mono" {...props}>
                {children}
              </code>
            ) : (
              <div className="relative my-4">
                <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
                  <code className="font-mono text-sm" {...props}>
                    {String(children).replace(/\n$/, '')}
                  </code>
                </pre>
              </div>
            )
          },
          // Custom styling for math blocks
          div({ className, children, ...props }) {
            if (className === 'math math-display') {
              return (
                <div className="math-display my-4 text-center overflow-x-auto" {...props}>
                  {children}
                </div>
              )
            }
            return <div className={className} {...props}>{children}</div>
          },
          // Custom styling for inline math
          span({ className, children, ...props }) {
            if (className === 'math math-inline') {
              return (
                <span className="math-inline" {...props}>
                  {children}
                </span>
              )
            }
            return <span className={className} {...props}>{children}</span>
          },
          // Better table styling
          table({ children }) {
            return (
              <div className="overflow-x-auto my-4">
                <table className="min-w-full border-collapse border border-border">
                  {children}
                </table>
              </div>
            )
          },
          th({ children }) {
            return (
              <th className="border border-border bg-muted px-4 py-2 text-left font-semibold">
                {children}
              </th>
            )
          },
          td({ children }) {
            return (
              <td className="border border-border px-4 py-2">
                {children}
              </td>
            )
          },
          // Better blockquote styling
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-primary pl-4 py-2 my-4 bg-muted/50 italic">
                {children}
              </blockquote>
            )
          }
        }}
      >
        {displayContent}
      </ReactMarkdown>
    </div>
  )
}