export interface Tenant {
  id: number
  name: string
  slug: string
  logo_url: string | null
  primary_color: string
  global_keywords: string
  schedule_cron: string
  topic_profile: string | null
  ai_categories: string | null
  max_article_age_days: number | null
  accepted_languages: string | null   // JSON list e.g. '["en","pt","fr"]'
  translation_language: string | null // e.g. "en"
  scrape_paused: boolean
  created_at: string
  updated_at: string
}

export interface Source {
  id: number
  tenant_id: number
  catalog_source_id: number | null
  name: string
  url: string
  type: 'rss' | 'scrape'
  css_selector: string | null
  keywords: string
  is_active: boolean
  last_scraped_at: string | null
  created_at: string
  updated_at: string
}

export interface ArticleSource {
  id: number
  name: string
}

export interface Article {
  id: number
  tenant_id: number
  source_id: number
  source: ArticleSource
  title: string
  translated_title: string | null
  excerpt: string | null
  summary: string | null
  url: string
  published_at: string | null
  scraped_at: string
  image_url: string | null
  category: string | null
  relevance_score: number
  relevance_reason: string | null
  is_read: boolean
  ai_enriched: boolean
  duplicate_of_id: number | null
  archived_at: string | null
  digest_id: number | null
}

export interface ArticleListResponse {
  items: Article[]
  total: number
  page: number
  size: number
  pages: number
}

export interface EmailConfig {
  id: number
  tenant_id: number
  smtp_host: string
  smtp_port: number
  smtp_user: string | null
  smtp_password: string | null
  from_email: string
  from_name: string
  recipients_json: string
  frequency: 'immediate' | 'daily' | 'weekly'
  send_time: string
  lookback_hours: number
  schedule_overrides: string | null
  subject_template: string
  intro_text: string | null
  is_active: boolean
  send_days: string | null  // JSON array e.g. '["mon","wed","fri"]'
  monthly_digest_enabled: boolean
  monthly_digest_day: number
  monthly_digest_time: string
  yearly_digest_enabled: boolean
  yearly_digest_month: number
  yearly_digest_day: number
  yearly_digest_time: string
  created_at: string
  updated_at: string
}

export interface DashboardStats {
  scraped_today: number
  pending_count: number
  enrichment_rate: number | null
  last_digest_at: string | null
  last_digest_subject: string | null
  next_send_at: string | null
  recent_runs_ok: number
  recent_runs_error: number
}

export interface ScrapeRun {
  id: number
  tenant_id: number
  source_id: number | null
  started_at: string
  completed_at: string | null
  articles_found: number
  articles_new: number
  status: 'running' | 'success' | 'partial' | 'error'
  error_message: string | null
}

export interface ScrapeRunListResponse {
  items: ScrapeRun[]
  total: number
  page: number
  size: number
}

export interface CatalogSource {
  id: number
  name: string
  url: string
  type: 'rss' | 'scrape'
  css_selector: string | null
  category: string
  description: string | null
  logo_url: string | null
  language: string
  country: string | null
  is_verified: boolean
  added_at: string
  updated_at: string
}
