import MarketingPage from '@/components/marketing-page';

export default function FAQsPage() {
  return (
    <MarketingPage
      eyebrow="FAQs"
      title="Common questions."
      description="Quick answers about setup, sources, security, and deploying with Recall."
      rows={[
        { label: 'What can I index?', detail: 'Docs, PDFs, websites, and structured knowledge sources.' },
        { label: 'Is it private?', detail: 'Workspaces are designed around controlled access to team knowledge.' },
        { label: 'Do I need an account?', detail: 'Yes. Sign in with a magic link to create or access your workspace.' },
        { label: 'Can I use APIs?', detail: 'Yes. Recall is built for product and engineering workflows.' },
      ]}
    />
  );
}
