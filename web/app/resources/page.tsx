import MarketingPage from '@/components/marketing-page';

export default function ResourcesPage() {
  return (
    <MarketingPage
      eyebrow="Resources"
      title="Guides for better retrieval."
      description="Short references for ingestion, chunking, evaluation, and deploying reliable answer flows."
      rows={[
        { label: 'Docs', detail: 'Set up sources, syncs, and API workflows.' },
        { label: 'Guides', detail: 'Patterns for chunking, prompts, citations, and search UX.' },
        { label: 'Examples', detail: 'Starter flows for internal docs, support, and research tools.' },
      ]}
    />
  );
}
