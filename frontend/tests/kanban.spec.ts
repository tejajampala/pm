import { expect, test, type Page } from "@playwright/test";

import { initialData } from "../src/lib/kanban";

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: /log in/i }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
}

async function reloadSignedIn(page: Page) {
  await page.reload();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
}

test.beforeEach(async ({ request }) => {
  const response = await request.put("/api/users/user/board", { data: initialData });
  expect(response.ok()).toBeTruthy();
});

test("shows the sign-in form first and rejects bad credentials", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: /log in/i }).click();
  await expect(page.getByText("Invalid username or password")).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(0);
});

test("loads the kanban board after login and stays signed in on reload", async ({ page }) => {
  await signIn(page);
  await reloadSignedIn(page);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
});

test("logs out and returns to the sign-in form", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: /log out/i }).click();
  await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
});

test("adds a card and keeps it after reload", async ({ page }) => {
  await signIn(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();

  await reloadSignedIn(page);
  await expect(page.locator('[data-testid^="column-"]').first().getByText("Playwright card")).toBeVisible();
});

test("edits a card and keeps the change after reload", async ({ page }) => {
  await signIn(page);
  await page.getByTestId("card-card-1").getByRole("button", { name: "Edit Align roadmap themes" }).click();
  await page.getByLabel("Edit card title").fill("Roadmap v2");
  await page.getByLabel("Edit card details").fill("Edited via e2e.");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByTestId("card-card-1").getByText("Roadmap v2")).toBeVisible();

  await reloadSignedIn(page);
  await expect(page.getByTestId("card-card-1").getByText("Roadmap v2")).toBeVisible();
  await expect(page.getByTestId("card-card-1").getByText("Edited via e2e.")).toBeVisible();
});

test("deletes a card and keeps it deleted after reload", async ({ page }) => {
  await signIn(page);
  await page.getByTestId("card-card-1").getByRole("button", { name: "Delete Align roadmap themes" }).click();
  await expect(page.getByTestId("card-card-1")).toHaveCount(0);

  await reloadSignedIn(page);
  await expect(page.getByTestId("card-card-1")).toHaveCount(0);
});

test("renames a column and keeps the name after reload", async ({ page }) => {
  await signIn(page);
  const title = page.getByTestId("column-col-backlog").getByLabel("Column title");
  await title.fill("Ideas");
  await title.press("Enter");
  await expect(title).toHaveValue("Ideas");

  await reloadSignedIn(page);
  await expect(page.getByTestId("column-col-backlog").getByLabel("Column title")).toHaveValue("Ideas");
});

test("moves a card between columns and keeps it there after reload", async ({ page }) => {
  await signIn(page);
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();

  await reloadSignedIn(page);
  await expect(page.getByTestId("column-col-review").getByTestId("card-card-1")).toBeVisible();
  await expect(page.getByTestId("column-col-backlog").getByTestId("card-card-1")).toHaveCount(0);
});

test("chat reaches the backend and shows its reply", async ({ page }) => {
  await signIn(page);
  await page.getByLabel("Message the assistant").fill("What is on my board?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("The AI assistant is not configured in this environment yet.")).toBeVisible();
});

test("chat applies a board update returned by the assistant", async ({ page }) => {
  await signIn(page);
  const updated = {
    ...initialData,
    cards: {
      ...initialData.cards,
      "card-ai": { id: "card-ai", title: "AI release task", details: "Created by assistant" },
    },
    columns: initialData.columns.map((column, index) =>
      index === 0 ? { ...column, cardIds: [...column.cardIds, "card-ai"] } : column
    ),
  };
  await page.route("**/api/ai/chat", (route) =>
    route.fulfill({ json: { reply: "Added the release task.", boardUpdate: updated } })
  );

  await page.getByLabel("Message the assistant").fill("Add a release task");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Added the release task.")).toBeVisible();
  await expect(page.getByTestId("column-col-backlog").getByText("AI release task")).toBeVisible();
});
