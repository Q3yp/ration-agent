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
    <div className="prose prose-sm max-w-none dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            return !inline && match ? (
              <SyntaxHighlighter
                style={oneDark}
                language={match[1]}
                PreTag="div"
                className="rounded-lg"
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code className="bg-gray-100 px-1 py-0.5 rounded text-sm" {...props}>
                {children}
              </code>
            )
          },
          // Custom styling for math blocks
          div({ node, className, children, ...props }) {
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
          span({ node, className, children, ...props }) {
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
                <table className="min-w-full border-collapse border border-gray-300">
                  {children}
                </table>
              </div>
            )
          },
          th({ children }) {
            return (
              <th className="border border-gray-300 bg-gray-50 px-4 py-2 text-left font-semibold">
                {children}
              </th>
            )
          },
          td({ children }) {
            return (
              <td className="border border-gray-300 px-4 py-2">
                {children}
              </td>
            )
          },
          // Better blockquote styling
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-blue-500 pl-4 py-2 my-4 bg-blue-50 italic">
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