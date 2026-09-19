import MarketingPage from '@/components/marketing-page';

export default function FeaturesPage() {
  return (
    <MarketingPage
      eyebrow="Features"
      title="Retrieval tools for product teams."
      description="Clean ingestion, private search, and answer flows in one focused workspace."
      rows={[
        { label: 'Ingest', detail: 'Connect docs, websites, PDFs, and internal knowledge sources.' },
        { label: 'Search', detail: 'Find relevant chunks with fast semantic and keyword retrieval.' },
        { label: 'Answer', detail: 'Generate grounded responses with citations and source context.' },
        { label: 'Control', detail: 'Keep access, syncs, and workspace permissions simple.' },
      ]}
    />
  );
}
