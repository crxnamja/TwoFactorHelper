#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libgen.h>
#include <mach-o/dyld.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    char path[4096];
    uint32_t size = sizeof(path);
    _NSGetExecutablePath(path, &size);

    // Resolve to Resources/twofactor.py relative to this binary
    char *dir = dirname(path);  // .app/Contents/MacOS
    char script[4096];
    snprintf(script, sizeof(script), "%s/../Resources/twofactor.py", dir);

    char *python = "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9";

    execl(python, "python3.9", script, NULL);
    return 1;
}
