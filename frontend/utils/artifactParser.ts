import { ArtifactData } from '@/types/chat';

/**
 * Parse artifact data from tool result content
 * Looks for [ARTIFACT_DATA] markers in the content
 */
export function parseArtifactData(content: string): ArtifactData | null {
  try {
    // Look for artifact data markers
    const artifactMatch = content.match(/\[ARTIFACT_DATA\]\s*(.*?)\s*\[\/ARTIFACT_DATA\]/s);
    
    if (!artifactMatch) {
      return null;
    }
    
    const artifactJson = artifactMatch[1].trim();
    const artifactData = JSON.parse(artifactJson);
    
    // Validate required fields
    if (!artifactData.title || !artifactData.html_content) {
      console.warn('Invalid artifact data: missing required fields');
      return null;
    }
    
    return {
      title: artifactData.title,
      description: artifactData.description || '',
      html_content: artifactData.html_content
    };
    
  } catch (error) {
    console.error('Error parsing artifact data:', error);
    return null;
  }
}

/**
 * Remove artifact data markers from content for display
 */
export function cleanContentForDisplay(content: string): string {
  return content.replace(/\[ARTIFACT_DATA\].*?\[\/ARTIFACT_DATA\]/s, '').trim();
}

/**
 * Check if content contains artifact data
 */
export function hasArtifactData(content: string): boolean {
  return /\[ARTIFACT_DATA\].*?\[\/ARTIFACT_DATA\]/s.test(content);
}