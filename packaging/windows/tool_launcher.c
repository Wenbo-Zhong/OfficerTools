/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Only Windows system DLLs are imported; no C/Python runtime is embedded.
 * Layout: <root>/tools/<category>/<tool>.exe -> <root>/办公工具箱.exe
 */
#ifndef UNICODE
#define UNICODE
#endif
#include <windows.h>

static wchar_t *last(wchar_t *text, wchar_t character) {
    wchar_t *found = NULL;
    while (*text) { if (*text == character) found = text; ++text; }
    return found;
}

static void append(wchar_t **destination, const wchar_t *text) {
    while (*text) *(*destination)++ = *text++;
    **destination = 0;
}

static DWORD launch(void) {
    HANDLE heap = GetProcessHeap();
    wchar_t *buffer = HeapAlloc(heap, HEAP_ZERO_MEMORY, 3 * 32768 * sizeof(wchar_t));
    if (!buffer) return 1;
    wchar_t *path = buffer, *name = buffer + 32768, *command = buffer + 65536;
    DWORD length = GetModuleFileNameW(NULL, path, 32768);
    if (!length || length >= 32768) return 1;
    wchar_t *separator = last(path, L'\\');
    if (!separator) return 1;
    lstrcpyW(name, separator + 1);
    wchar_t *extension = last(name, L'.');
    if (extension) *extension = 0;
    for (int level = 0; level < 3; ++level) {
        separator = last(path, L'\\');
        if (!separator) return 1;
        *separator = 0;
    }
    if (lstrlenW(path) + 20 >= 32768) return 1;
    wchar_t *end = path + lstrlenW(path);
    append(&end, L"\\办公工具箱.exe");
    if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL, L"未找到办公工具箱主程序。请保留完整发布包的目录结构。", L"OfficerTools", MB_OK | MB_ICONERROR);
        return 1;
    }
    /* Preserve the original argument tail verbatim, including Windows quoting. */
    const wchar_t *tail = GetCommandLineW();
    if (*tail == L'"') {
        ++tail;
        while (*tail && *tail != L'"') ++tail;
        if (*tail) ++tail;
    } else {
        while (*tail && *tail != L' ' && *tail != L'\t') ++tail;
    }
    while (*tail == L' ' || *tail == L'\t') ++tail;
    if (lstrlenW(path) + lstrlenW(name) + lstrlenW(tail) + 40 >= 32768) return 1;
    end = command;
    append(&end, L"\""); append(&end, path);
    append(&end, L"\" --tool-exe \""); append(&end, name);
    append(&end, L"\" "); append(&end, tail);
    STARTUPINFOW startup;
    volatile unsigned char *zero = (volatile unsigned char *)&startup;
    for (unsigned int i = 0; i < sizeof(startup); ++i) zero[i] = 0;
    PROCESS_INFORMATION process;
    startup.cb = sizeof(startup);
    BOOL started = CreateProcessW(path, command, NULL, NULL, FALSE, 0, NULL, NULL, &startup, &process);
    HeapFree(heap, 0, buffer);
    if (!started) {
        MessageBoxW(NULL, L"无法启动办公工具箱主程序。请重新解压完整发布包后重试。", L"OfficerTools", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    return code;
}

void WINAPI launcher_start(void) {
    ExitProcess(launch());
}
