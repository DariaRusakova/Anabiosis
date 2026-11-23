#include "ElementalWeaponEditorLibrary.h"
#include "Engine/Blueprint.h"

bool UElementalWeaponEditorLibrary::IsBlueprintCompiled(const UBlueprint* Blueprint)
{
#if WITH_EDITOR
    // IsUpToDate accepts both clean success and success with warnings. A stale
    // generated class after a compiler error must never count as success.
    return IsValid(Blueprint) && Blueprint->IsUpToDate() && Blueprint->GeneratedClass != nullptr;
#else
    return false;
#endif
}
