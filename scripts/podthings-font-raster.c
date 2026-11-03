/* SPDX-License-Identifier: GPL-2.0-or-later
 * Host-only FreeType rasterizer. Not linked into the iPod firmware.
 */
#include <stdio.h>
#include <stdlib.h>
#include <ft2build.h>
#include FT_FREETYPE_H

int main(int argc, char **argv)
{
    FT_Library library;
    FT_Face face;
    if (argc != 3 || FT_Init_FreeType(&library))
        return 1;
    if (FT_New_Face(library, argv[1], 0, &face) ||
        FT_Select_Charmap(face, FT_ENCODING_UNICODE) ||
        FT_Set_Pixel_Sizes(face, 0, atoi(argv[2])))
        return 2;
    FT_UInt index;
    FT_ULong code = FT_Get_First_Char(face, &index);
    while (index && code <= 0xffff) {
        if (code >= 32 && !FT_Load_Char(face, code,
                FT_LOAD_RENDER | FT_LOAD_TARGET_MONO | FT_LOAD_MONOCHROME)) {
            FT_GlyphSlot g = face->glyph;
            FT_Bitmap *b = &g->bitmap;
            printf("%lu %u %u %d %d %ld ", code, b->width, b->rows,
                   g->bitmap_left, g->bitmap_top, (g->advance.x + 32) >> 6);
            if (!b->rows || !b->width)
                putchar('-');
            for (unsigned int y = 0; y < b->rows; y++) {
                const unsigned char *row = b->buffer +
                    (b->pitch >= 0 ? y * b->pitch :
                     (b->rows - 1 - y) * -b->pitch);
                for (unsigned int x = 0; x < (b->width + 7) / 8; x++)
                    printf("%02X", row[x]);
            }
            putchar('\n');
        }
        code = FT_Get_Next_Char(face, code, &index);
    }
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    return 0;
}
