/*
 * mm_strings_compat.h
 *
 * Windows/MinGW compatibility shim, force-included (gcc -include) on the
 * Windows build only. MinGW's <strings.h> does not declare bzero(), a
 * BSD/glibc-ism used verbatim by the vendored fsk.c and
 * simple-tone-generator.c. Providing it here lets those upstream sources
 * compile WITHOUT any edits to the vendored files.
 */

#ifndef MM_STRINGS_COMPAT_H
#define MM_STRINGS_COMPAT_H

#include <string.h>

#ifndef bzero
#define bzero(p, n)  memset((p), 0, (n))
#endif

#endif /* MM_STRINGS_COMPAT_H */
