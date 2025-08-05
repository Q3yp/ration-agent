import { ArtifactData } from '@/types/chat';

/**
 * Parse artifact data from tool result content
 * Looks for [ARTIFACT_DATA] markers in the content
 */
export function parseArtifactData(content: string): ArtifactData | null {
  try {
    // Look for artifact data markers - capture everything between the markers
    const artifactMatch = content.match(/\[ARTIFACT_DATA\]([\s\S]*?)\[\/ARTIFACT_DATA\]/);

    if (!artifactMatch) {
      return null;
    }

    const artifactJson = artifactMatch[1].trim();
    console.log('Raw captured JSON:', JSON.stringify(artifactJson.substring(0, 200)));
    console.log('JSON length:', artifactJson.length);

    // Handle empty artifact data
    if (!artifactJson) {
      console.warn('Empty artifact data found');
      return null;
    }

    const artifactData = JSON.parse(artifactJson);

    // Validate required fields
    if (!artifactData.title || !artifactData.html_content) {
      console.warn('Invalid artifact data: missing required fields', {
        hasTitle: !!artifactData.title,
        hasHtmlContent: !!artifactData.html_content,
        keys: Object.keys(artifactData)
      });
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
  return content.replace(/\[ARTIFACT_DATA\][\s\S]*?\[\/ARTIFACT_DATA\]/, '').trim();
}

/**
 * Check if content contains artifact data
 */
export function hasArtifactData(content: string): boolean {
  return /\[ARTIFACT_DATA\][\s\S]*?\[\/ARTIFACT_DATA\]/.test(content);
}