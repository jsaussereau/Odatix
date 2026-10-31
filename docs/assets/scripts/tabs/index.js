const TABS_SELECTIONS_KEY = 'tabSelections';

function getSelections() {
  try {
    const raw = window.localStorage?.getItem(TABS_SELECTIONS_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function saveSelection(group, tabId) {
  try {
    const selections = getSelections();
    selections[group] = tabId;
    window.localStorage?.setItem(TABS_SELECTIONS_KEY, JSON.stringify(selections));
  } catch {
    // ignore storage issues
  }
}

function setActiveForGroup(tabGroup, tabId) {
  const panels = document.querySelectorAll(`.tab-panel[data-tab-group="${CSS.escape(tabGroup)}"]`);
  panels.forEach((panel) => setActiveForPanel(panel, tabId));
}

function setActiveForPanel(panel, tabId) {
  const panelButtons = Array.from(panel.querySelectorAll(':scope > .tab-nav > .tab-nav-button'));
  const panelItems = Array.from(panel.querySelectorAll(':scope > .tab-content > .tab-item'));

  // A panel without this tab keeps its current selection
  if (!panelButtons.some((button) => button.dataset.tabItem === tabId)) return;

  panelButtons.forEach((button) => {
    const isActive = button.dataset.tabItem === tabId;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  panelItems.forEach((item) => {
    const isActive = item.dataset.tabItem === tabId;
    item.classList.toggle('active', isActive);
    item.hidden = !isActive;
  });
}

function syncIdenticalTabs(tabId, sourceGroup) {
  const buttons = Array.from(document.querySelectorAll('.tab-nav-button'));
  const matchingGroups = new Set(
    buttons
      .filter((button) => button.dataset.tabItem === tabId)
      .map((button) => button.dataset.tabGroup)
      .filter(Boolean),
  );

  matchingGroups.forEach((group) => {
    setActiveForGroup(group, tabId);
    if (group !== sourceGroup) {
      saveSelection(group, tabId);
    }
  });
}

function bindTabButtons() {
  const buttons = Array.from(document.querySelectorAll('.tab-nav-button'));
  buttons.forEach((button) => {
    button.addEventListener('click', (e) => {
      const tabGroup = button.dataset.tabGroup;
      const tabId = button.dataset.tabItem;
      if (!tabGroup || !tabId) return;

      const yBefore = e.currentTarget.getBoundingClientRect().top;

      setActiveForGroup(tabGroup, tabId);
      syncIdenticalTabs(tabId, tabGroup);
      saveSelection(tabGroup, tabId);

      const yAfter = e.currentTarget.getBoundingClientRect().top;
      window.scrollTo(window.scrollX, window.scrollY + (yAfter - yBefore));
    });
  });
}

function restoreTabSelections() {
  const selections = getSelections();
  Object.keys(selections).forEach((tabGroup) => {
    const tabItem = selections[tabGroup];
    if (!tabItem) return;

    setActiveForGroup(tabGroup, tabItem);
    syncIdenticalTabs(tabItem, tabGroup);
  });
}

window.addEventListener('DOMContentLoaded', () => {
  bindTabButtons();
  restoreTabSelections();
});