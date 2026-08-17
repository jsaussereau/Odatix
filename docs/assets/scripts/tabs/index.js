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
  const allGroupElements = Array.from(document.querySelectorAll(`[data-tab-group="${CSS.escape(tabGroup)}"]`));
  const groupButtons = allGroupElements.filter((el) => el.classList.contains('tab-nav-button'));
  const groupItems = allGroupElements.filter((el) => el.classList.contains('tab-item'));

  const targetExists = allGroupElements.some((el) => el.dataset.tabItem === tabId);
  const targetId = targetExists
    ? tabId
    : (groupButtons[0]?.dataset.tabItem || groupItems[0]?.dataset.tabItem || tabId);

  groupButtons.forEach((button) => {
    const isActive = button.dataset.tabItem === targetId;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  groupItems.forEach((item) => {
    const isActive = item.dataset.tabItem === targetId;
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