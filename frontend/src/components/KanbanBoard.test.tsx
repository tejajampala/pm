import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? "GET";

        return {
          ok: true,
          json: async () => {
            if (method === "PUT") {
              return JSON.parse(String(init?.body ?? "{}"));
            }

            return initialData;
          },
        };
      })
    );
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

  it("renames a column", async () => {
    render(<KanbanBoard />);
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoard />);
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(within(column).getByText("New card")).toBeInTheDocument();

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
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
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => ({
      ok: true,
      json: async () =>
        init?.method === "POST"
          ? { reply: "Added the release task.", boardUpdate: updatedBoard }
          : initialData,
    }));
    vi.stubGlobal("fetch", fetchMock);

    render(<KanbanBoard username="user" />);
    await userEvent.type(screen.getByLabelText("Message the assistant"), "Add a release task");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Added the release task.")).toBeInTheDocument();
    expect(await screen.findByText("AI release task")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ai/chat",
      expect.objectContaining({ method: "POST" })
    );
  });
});
