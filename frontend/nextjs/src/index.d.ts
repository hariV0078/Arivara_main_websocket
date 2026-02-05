declare module 'gpt-researcher-ui' {
  import React from 'react';

  export interface Arivara_researcherProps {
    apiUrl?: string;
    apiKey?: string;
    defaultPrompt?: string;
    onResultsChange?: (results: any) => void;
    theme?: any;
  }

  export const Arivara_researcher: React.FC<Arivara_researcherProps>;
}