-- ============================================================
-- Migration 002 — Per-provider API key columns
-- Run in the Supabase SQL editor after 001_initial_schema.sql
-- ============================================================

alter table public.user_settings
  add column if not exists openai_key_encrypted    text not null default '',
  add column if not exists openai_key_last4         text not null default '',
  add column if not exists openai_key_valid         boolean not null default false,
  add column if not exists anthropic_key_encrypted  text not null default '',
  add column if not exists anthropic_key_last4      text not null default '',
  add column if not exists anthropic_key_valid      boolean not null default false,
  add column if not exists gemini_key_encrypted     text not null default '',
  add column if not exists gemini_key_last4         text not null default '',
  add column if not exists gemini_key_valid         boolean not null default false;
