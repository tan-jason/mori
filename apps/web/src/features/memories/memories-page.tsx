import { useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { PageErrorState, PageLoadingState } from "../../components/async-state";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";
import { useLearnerSession } from "../../app/use-learner-session";
import type { LearnerFileEntry, LearnerFilePage } from "../../domain/learning";
import { useLearnerFile } from "./use-memories";

function LearnerFileCard({ entry }: { entry: LearnerFileEntry }) {
  const { gateway } = useAppDependencies();
  const { languageProfile } = useLanguageProfile();
  const { learner } = useLearnerSession();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(entry.text);
  const [validationError, setValidationError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const queryKey = ["learner-file", languageProfile.id];
  const edit = useMutation({
    mutationFn: (text: string) => gateway.editLearnerFileEntry({
      languageProfileId: languageProfile.id, entryId: entry.id,
      expectedVersion: entry.version, text, csrfToken: learner.csrfToken,
    }),
    onSuccess: (updated) => {
      queryClient.setQueryData<InfiniteData<LearnerFilePage>>(queryKey, (data) => data && ({
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          entries: page.entries.map((item) => item.id === updated.id ? updated : item),
        })),
      }));
      setEditing(false);
      setValidationError("");
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: () => void queryClient.invalidateQueries({ queryKey }),
  });
  const remove = useMutation({
    mutationFn: () => gateway.deleteLearnerFileEntry({
      languageProfileId: languageProfile.id, entryId: entry.id,
      expectedVersion: entry.version, csrfToken: learner.csrfToken,
    }),
    onSuccess: () => {
      queryClient.setQueryData<InfiniteData<LearnerFilePage>>(queryKey, (data) => data && ({
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          entries: page.entries.filter((item) => item.id !== entry.id),
        })),
      }));
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: () => void queryClient.invalidateQueries({ queryKey }),
  });
  const busy = edit.isPending || remove.isPending;
  const onSave = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const clean = draft.trim();
    if (!clean || clean.length > 240) {
      setValidationError("Keep this entry between 1 and 240 characters.");
      return;
    }
    if (clean === entry.text) {
      setEditing(false);
      return;
    }
    edit.mutate(clean);
  };
  const expires = entry.expiresAt
    ? `Expires ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(entry.expiresAt))}`
    : "Kept until you delete it";
  const errorMessage = validationError || (edit.error instanceof Error ? edit.error.message : "") ||
    (remove.error instanceof Error ? remove.error.message : "");

  return (
    <article className="memory-card learner-file-card">
      <span className={`learner-file-kind learner-file-kind-${entry.kind}`}>
        {entry.kind === "learning" ? "Learning" : "Insight"}
      </span>
      <div className="learner-file-card-body">
        {editing ? (
          <form onSubmit={onSave} className="learner-file-edit">
            <label htmlFor={`learner-file-${entry.id}`}>Edit {entry.kind}</label>
            <textarea id={`learner-file-${entry.id}`} value={draft} maxLength={240} rows={3}
              onChange={(event) => { setDraft(event.target.value); setValidationError(""); edit.reset(); }} />
            <div className="learner-file-actions">
              <button className="button button-primary" type="submit" disabled={busy}>Save</button>
              <button className="button button-quiet" type="button" disabled={busy}
                onClick={() => { setEditing(false); setDraft(entry.text); edit.reset(); }}>Cancel</button>
            </div>
          </form>
        ) : (
          <>
            <p className="learner-file-text">{entry.text}</p>
            <p className="memory-source">
              {entry.origin === "learner_edit" ? "Edited by you" : "Captured from a conversation"} · {expires}
            </p>
          </>
        )}
        {errorMessage && <p className="learner-file-error" role="alert">{errorMessage}</p>}
        {confirmDelete && !editing && (
          <div className="learner-file-confirm">
            <p>Delete this {entry.kind}? Mori will stop using it in future conversations.</p>
            <button className="button button-danger-quiet" type="button" disabled={busy}
              onClick={() => remove.mutate()}>Delete {entry.kind}</button>
            <button className="button button-quiet" type="button" disabled={busy}
              onClick={() => { setConfirmDelete(false); remove.reset(); }}>Cancel</button>
          </div>
        )}
      </div>
      {!editing && !confirmDelete && (
        <div className="learner-file-actions">
          <button className="button button-quiet" type="button" onClick={() => { setEditing(true); setDraft(entry.text); }}>Edit</button>
          <button className="button button-danger-quiet" type="button" onClick={() => setConfirmDelete(true)}>Delete</button>
        </div>
      )}
    </article>
  );
}

export function MemoriesPage() {
  const learnerFile = useLearnerFile();

  if (learnerFile.isPending) return <PageLoadingState />;
  if (learnerFile.isError) return <PageErrorState onRetry={() => void learnerFile.refetch()} />;
  const entries = learnerFile.data.pages.flatMap((page) => page.entries);

  return (
    <div className="detail-page memories-page">
      <header className="detail-hero detail-hero-compact">
        <p className="eyebrow">Your conversation record</p>
        <h1>Learner file</h1>
        <p className="detail-summary">
          Learnings describe the language you practiced and how it served your lesson goal.
          Insights are details you shared about your interests or work that can help Mori
          make future conversations more relevant. You can correct or delete either one.
        </p>
      </header>

      <section className="section-block" aria-labelledby="learner-file-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Captured after conversations</p>
            <h2 id="learner-file-title">Your entries</h2>
          </div>
          <span className="count-pill">{entries.length}</span>
        </div>
        {entries.length === 0 ? (
          <div className="privacy-note"><strong>Nothing captured yet</strong>
            <p>Learnings and insights from completed conversations will appear here.</p></div>
        ) : (
          <div className="memory-list">
            {entries.map((entry) => <LearnerFileCard key={entry.id} entry={entry} />)}
          </div>
        )}
        {learnerFile.hasNextPage && (
          <button className="button button-quiet learner-file-more" type="button"
            disabled={learnerFile.isFetchingNextPage}
            onClick={() => void learnerFile.fetchNextPage()}>
            {learnerFile.isFetchingNextPage ? "Loading..." : "Load older entries"}
          </button>
        )}
        {learnerFile.isFetchNextPageError && <p role="alert">Older entries could not be loaded. Try again.</p>}
      </section>

      <aside className="privacy-note">
        <strong>You control what Mori remembers</strong>
        <p>Insights expire after 90 days. Changes take effect before the next call. Finish an active call before editing or deleting an entry.</p>
      </aside>
    </div>
  );
}
