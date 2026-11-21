#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ElementalWeaponEditorLibrary.generated.h"

class UBlueprint;

/** Authoring checks whose native Blueprint properties are protected in Python. */
UCLASS()
class ANABIOSIS_API UElementalWeaponEditorLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** True only for a successfully compiled Blueprint with a generated class. */
    UFUNCTION(BlueprintPure, Category="Elemental Weapons|Editor", meta=(DevelopmentOnly))
    static bool IsBlueprintCompiled(const UBlueprint* Blueprint);
};
