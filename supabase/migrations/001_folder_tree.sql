-- Run in Supabase Dashboard → SQL Editor (entire file).

-- Columns for folder tree + chat organization
alter table public.folders
  add column if not exists parent_id uuid references public.folders (id) on delete cascade;

alter table public.chats
  add column if not exists folder_id uuid references public.folders (id) on delete set null;

create index if not exists folders_parent_id_idx on public.folders (parent_id);
create index if not exists chats_folder_id_idx on public.chats (folder_id);

-- Row level security (required for rename, move, subfolders to save)
alter table public.folders enable row level security;
alter table public.chats enable row level security;

-- Folders policies
drop policy if exists "folders_select_own" on public.folders;
drop policy if exists "folders_insert_own" on public.folders;
drop policy if exists "folders_update_own" on public.folders;
drop policy if exists "folders_delete_own" on public.folders;

create policy "folders_select_own" on public.folders
  for select using (auth.uid() = user_id);

create policy "folders_insert_own" on public.folders
  for insert with check (auth.uid() = user_id);

create policy "folders_update_own" on public.folders
  for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "folders_delete_own" on public.folders
  for delete using (auth.uid() = user_id);

-- Chats policies (folder_id updates need update policy)
drop policy if exists "chats_select_own" on public.chats;
drop policy if exists "chats_insert_own" on public.chats;
drop policy if exists "chats_update_own" on public.chats;
drop policy if exists "chats_delete_own" on public.chats;

create policy "chats_select_own" on public.chats
  for select using (auth.uid() = user_id);

create policy "chats_insert_own" on public.chats
  for insert with check (auth.uid() = user_id);

create policy "chats_update_own" on public.chats
  for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "chats_delete_own" on public.chats
  for delete using (auth.uid() = user_id);
