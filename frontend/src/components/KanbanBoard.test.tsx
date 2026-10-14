import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const getFirstColumn = async () => (await screen.findAllByTestId(/column-/i))[0];

const putBodies = (fetchMock: { mock: { calls: unknown[][] } }) =>
  fetchMock.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "PUT")
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));

const stubFetch = (handler: (method: string, body?: string) => Promise<{ ok: boolean; json: () => Promise<unknown> }>) => {
  const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
    handler(init?.method ?? "GET", init?.body as string | undefined)
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

// A backend that serves initialData and echoes every saved board back.
const stubWorkingBackend = () =>
  stubFetch(async (method, body) => ({
    ok: true,
    json: async () => (method === "PUT" ? JSON.parse(String(body)) : initialData),
  }));

describe("KanbanBoard", () => {
  beforeEach(() => {
    stubWorkingBackend();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the board from the backend API for the signed-in user", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        columns: [{ id: "col-backlog", title: "API Board", cardIds: ["card-1"] }],
        cards: {
          "card-1": { id: "card-1", title: "API card", details: "Loaded from server" },
        },
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<KanbanBoard username="user" />);

    expect(fetchMock).toHaveBeenCalledWith("/api/users/user/board", { cache: "no-store" });
    expect(await screen.findByText("API Board")).toBeInTheDocument();
    expect(screen.getByText("API card")).toBeInTheDocument();
  });

  it("renders five columns", async () => {
    render(<KanbanBoard />);
    await waitFor(() => expect(screen.queryByText("Loading board...")).not.toBeInTheDocument());
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column and saves once when editing is finished", async () => {
    const fetchMock = stubWorkingBackend();
    render(<KanbanBoard />);
    const input = within(await getFirstColumn()).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
    expect(putBodies(fetchMock)).toHaveLength(0);

    await userEvent.tab();

    await waitFor(() => expect(putBodies(fetchMock)).toHaveLength(1));
    expect(putBodies(fetchMock)[0].columns[0].title).toBe("New Name");
  });

  it("restores the previous column title when it is cleared", async () => {
    const fetchMock = stubFetch(async () => ({ ok: true, json: async () => initialData }));
    render(<KanbanBoard />);
    const input = within(await getFirstColumn()).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.tab();

    expect(input).toHaveValue("Backlog");
    expect(putBodies(fetchMock)).toHaveLength(0);
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoard />);
    const column = await getFirstColumn();
    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), "New card");
    await userEvent.type(within(column).getByPlaceholderText(/details/i), "Notes");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(within(column).getByText("New card")).toBeInTheDocument();

    await userEvent.click(within(column).getByRole("button", { name: /delete new card/i }));

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
  });

  it("edits a card and saves the change", async () => {
    const fetchMock = stubWorkingBackend();
    render(<KanbanBoard />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Align roadmap themes" }));

    const title = screen.getByLabelText("Edit card title");
    await userEvent.clear(title);
    await userEvent.type(title, "Roadmap v2");
    const details = screen.getByLabelText("Edit card details");
    await userEvent.clear(details);
    await userEvent.type(details, "Refined scope");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(screen.getByText("Roadmap v2")).toBeInTheDocument();
    expect(screen.getByText("Refined scope")).toBeInTheDocument();
    await waitFor(() => expect(putBodies(fetchMock)).toHaveLength(1));
    expect(putBodies(fetchMock)[0].cards["card-1"]).toEqual({
      id: "card-1",
      title: "Roadmap v2",
      details: "Refined scope",
    });
  });

  it("cancels a card edit without saving", async () => {
    const fetchMock = stubFetch(async () => ({ ok: true, json: async () => initialData }));
    render(<KanbanBoard />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Align roadmap themes" }));
    await userEvent.type(screen.getByLabelText("Edit card title"), " changed");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByText("Align roadmap themes")).toBeInTheDocument();
    expect(putBodies(fetchMock)).toHaveLength(0);
  });

  it("shows an error with retry and no editable board when loading fails", async () => {
    let attempts = 0;
    stubFetch(async () => {
      attempts += 1;
      return attempts === 1
        ? { ok: false, json: async () => ({}) }
        : { ok: true, json: async () => initialData };
    });
    render(<KanbanBoard />);

    expect(await screen.findByText("Board request failed with status undefined")).toBeInTheDocument();
    expect(screen.queryAllByTestId(/column-/i)).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("shows an error banner when saving fails", async () => {
    stubFetch(async (method) => ({
      ok: method !== "PUT",
      json: async () => initialData,
    }));
    render(<KanbanBoard />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete Align roadmap themes" }));

    expect(await screen.findByText("Unable to save the deleted card.")).toBeInTheDocument();
  });

  it("sends saves one at a time and in order", async () => {
    let releaseFirstSave: () => void = () => {};
    let putCount = 0;
    const fetchMock = stubFetch(async (method, body) => {
      if (method !== "PUT") {
        return { ok: true, json: async () => initialData };
      }
      putCount += 1;
      if (putCount === 1) {
        await new Promise<void>((resolve) => {
          releaseFirstSave = resolve;
        });
      }
      return { ok: true, json: async () => JSON.parse(String(body)) };
    });
    render(<KanbanBoard />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete Align roadmap themes" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete Gather customer signals" }));

    await waitFor(() => expect(putBodies(fetchMock)).toHaveLength(1));
    expect(Object.keys(putBodies(fetchMock)[0].cards)).not.toContain("card-1");

    releaseFirstSave();

    await waitFor(() => expect(putBodies(fetchMock)).toHaveLength(2));
    expect(Object.keys(putBodies(fetchMock)[1].cards)).not.toContain("card-2");
  });

  it("applies a board update returned by the AI assistant", async () => {
    const updatedBoard = {
      ...initialData,
      cards: {
        ...initialData.cards,
        "card-ai": { id: "card-ai", title: "AI release task", details: "Created by assistant" },
      },
      columns: initialData.columns.map((column, index) =>
        index === 0 ? { ...column, cardIds: [...column.cardIds, "card-ai"] } : column
      ),
    };
    const fetchMock = stubFetch(async (method) => ({
      ok: true,
      json: async () =>
        method === "POST" ? { reply: "Added the release task.", boardUpdate: updatedBoard } : initialData,
    }));

    render(<KanbanBoard username="user" />);
    await userEvent.type(await screen.findByLabelText("Message the assistant"), "Add a release task");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Added the release task.")).toBeInTheDocument();
    expect(await screen.findByText("AI release task")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ai/chat",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("shows a readable error when the AI request fails with a non-JSON response", async () => {
    stubFetch(async (method) =>
      method === "POST"
        ? { ok: false, json: async () => { throw new SyntaxError("not json"); } }
        : { ok: true, json: async () => initialData }
    );
    render(<KanbanBoard username="user" />);
    await userEvent.type(await screen.findByLabelText("Message the assistant"), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("AI request failed with status");
  });
});
