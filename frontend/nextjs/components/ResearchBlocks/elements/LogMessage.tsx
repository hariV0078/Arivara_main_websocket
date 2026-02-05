// LogMessage.tsx
import Accordion from '../../Task/Accordion';
import { useEffect, useState } from 'react';
import { markdownToHtml } from '../../../helpers/markdownHelper';
import ImagesAlbum from '../../Images/ImagesAlbum';
import Image from "next/image";

type ProcessedData = {
  field: string;
  htmlContent: string;
  isMarkdown: boolean;
};

type Log = {
  header: string;
  text: string;
  processedData?: ProcessedData[];
  metadata?: any;
};

interface LogMessageProps {
  logs: Log[];
}

const LogMessage: React.FC<LogMessageProps> = ({ logs }) => {
  const [processedLogs, setProcessedLogs] = useState<Log[]>([]);

  useEffect(() => {
    const processLogs = async () => {
      if (!logs) return;
      
      const newLogs = await Promise.all(
        logs.map(async (log) => {
          try {
            if (log.header === 'differences' && log.text) {
              const data = JSON.parse(log.text).data;
              const processedData = await Promise.all(
                Object.keys(data).map(async (field) => {
                  const fieldValue = data[field].after || data[field].before;
                  if (!plainTextFields.includes(field)) {
                    const htmlContent = await markdownToHtml(fieldValue);
                    return { field, htmlContent, isMarkdown: true };
                  }
                  return { field, htmlContent: fieldValue, isMarkdown: false };
                })
              );
              return { ...log, processedData };
            }
            return log;
          } catch (error) {
            console.error('Error processing log:', error);
            return log;
          }
        })
      );
      setProcessedLogs(newLogs);
    };

    processLogs();
  }, [logs]);

  return (
    <>
      {processedLogs.map((log, index) => {
        if (log.header === 'subquery_context_window' || log.header === 'differences') {
          return <Accordion key={index} logs={[log]} />;
        } else if (log.header === 'http_request') {
          // Special styling for HTTP request logs
          const metadata = log.metadata || {};
          const statusCode = metadata.status_code || 0;
          const isSuccess = statusCode >= 200 && statusCode < 300;
          const isError = statusCode >= 400;
          
          return (
            <div
              key={index}
              className={`w-full max-w-4xl mx-auto rounded-lg pt-2 mt-2 pb-2 px-4 shadow-md ${
                isError ? 'bg-red-900/30 border border-red-500/50' :
                isSuccess ? 'bg-green-900/20 border border-green-500/30' :
                'bg-blue-900/20 border border-blue-500/30'
              }`}
            >
              <div className="flex items-center gap-2 py-2">
                <span className="text-xs font-mono text-gray-400">
                  {metadata.api_provider || 'API'}
                </span>
                <span className={`text-xs font-semibold ${
                  isError ? 'text-red-400' :
                  isSuccess ? 'text-green-400' :
                  'text-blue-400'
                }`}>
                  {metadata.method} {statusCode}
                </span>
              </div>
              <p className="py-1 text-sm leading-relaxed text-gray-300 dark:text-gray-300 font-mono">
                {log.text}
              </p>
            </div>
          );
        } else if (log.header !== 'selected_images' && log.header !== 'scraping_images') {
          return (
            <div
              key={index}
              className="w-full max-w-4xl mx-auto rounded-lg pt-2 mt-3 pb-2 px-4 bg-gray-900 shadow-md"
            >
              <p className="py-3 text-base leading-relaxed text-white dark:text-white">
                {log.text}
              </p>
            </div>
          );
        }
        return null;
      })}
    </>
  );
};

const plainTextFields = ['task', 'sections', 'headers', 'sources', 'research_data'];

export default LogMessage;