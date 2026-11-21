#pragma once

#include "CoreMinimal.h"
#include "AnabiosisCharacter.h"
#include "ElementalFirstPersonCharacter.generated.h"

class UElementalWeaponComponent;
class UElementalWeaponDefinition;

UCLASS()
class ANABIOSIS_API AElementalFirstPersonCharacter : public AAnabiosisCharacter
{
    GENERATED_BODY()
public:
    AElementalFirstPersonCharacter();
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Elemental Weapons")
    TArray<TObjectPtr<UElementalWeaponDefinition>> WeaponLoadout;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Elemental Weapons")
    TObjectPtr<UElementalWeaponComponent> ElementalWeapons;
protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual void UnPossessed() override;
};
