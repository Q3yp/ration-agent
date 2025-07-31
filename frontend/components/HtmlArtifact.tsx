'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ExternalLink, Maximize2, Minimize2 } from 'lucide-react';

interface HtmlArtifactProps {
  title?: string;
  description?: string;
  htmlContent: string;
  onClose?: () => void;
}

export default function HtmlArtifact({ title = "HTML Artifact", description, htmlContent, onClose }: HtmlArtifactProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (iframeRef.current && htmlContent) {
      // Use srcdoc instead of data URL to avoid security restrictions
      iframeRef.current.srcdoc = htmlContent;
    }
  }, [htmlContent]);

  const openInNewTab = () => {
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const newWindow = window.open(url, '_blank');
    if (newWindow) {
      // Clean up the object URL after a short delay
      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 1000);
    }
  };

  return (
    <Card className={`w-full h-full flex flex-col transition-all duration-200 ${isExpanded ? 'fixed inset-4 z-50 bg-white' : ''}`}>
      <CardHeader className="pb-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg font-semibold text-gray-900">
              {title}
            </CardTitle>
            {description && (
              <p className="text-sm text-gray-600 mt-1">{description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={openInNewTab}
              className="p-2"
            >
              <ExternalLink className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-2"
            >
              {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </Button>
            {onClose && (
              <Button
                variant="outline"
                size="sm"
                onClick={onClose}
                className="p-2"
              >
                ✕
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0 flex-1 min-h-0">
        <div className={`relative bg-gray-50 overflow-hidden h-full ${
          isExpanded ? '' : 'rounded-b-lg'
        }`}>
          <iframe
            ref={iframeRef}
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin allow-forms"
            title={title}
          />
        </div>
      </CardContent>
    </Card>
  );
}